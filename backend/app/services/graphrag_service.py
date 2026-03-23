"""GraphRAG 构图服务。

该模块负责把知识库文档转成 GraphRAG CLI 所需的工作目录，执行构图命令，并回收结果产物。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from app.core.config import settings
from app.models.schemas import KnowledgeDocumentDetail
from app.services.object_storage import object_storage_service


class GraphRAGService:
    def __init__(self, workspace_dir: Path) -> None:
        self.workspace_dir = workspace_dir
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        return shutil.which("graphrag") is not None

    def build_index(
        self,
        *,
        job_id: str,
        documents: list[KnowledgeDocumentDetail],
        method: str = "standard",
    ) -> dict[str, Any]:
        """为指定文档集构建一份可查询的 GraphRAG 索引。"""
        if not self.is_available():
            raise ValueError("GraphRAG CLI 未安装，无法执行图谱构建。")
        if not settings.dashscope_api_key:
            raise ValueError("DASHSCOPE_API_KEY 未配置，无法执行 GraphRAG 构建。")
        if not documents:
            raise ValueError("至少需要一份文档才能执行 GraphRAG 构建。")

        workspace = (self.workspace_dir / job_id).resolve()
        workspace.mkdir(parents=True, exist_ok=True)

        env = self._build_env()
        self._run_command(
            [
                "graphrag",
                "init",
                "-r",
                str(workspace),
                "-f",
                "-m",
                settings.graphrag_chat_model,
                "-e",
                settings.graphrag_embedding_model,
            ],
            env=env,
            workspace=workspace,
            stage="init",
        )
        self._configure_workspace(workspace)
        self._write_input_files(workspace, documents)
        self._run_command(
            ["graphrag", "index", "-r", str(workspace), "-m", method],
            env=env,
            workspace=workspace,
            stage="index",
        )

        result = self._summarize_workspace(workspace, method, documents)
        result["archive_object_key"] = self._archive_workspace(job_id, workspace)
        result["graph_available"] = result["artifact_counts"].get("entities", 0) > 0
        return result

    def _build_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["GRAPHRAG_API_KEY"] = settings.dashscope_api_key
        env["GRAPHRAG_API_BASE"] = settings.graphrag_api_base
        env["TOKENIZERS_PARALLELISM"] = "false"
        return env

    def _configure_workspace(self, workspace: Path) -> None:
        settings_path = workspace / "settings.yaml"
        data = yaml.safe_load(settings_path.read_text(encoding="utf-8"))

        completion = data["completion_models"]["default_completion_model"]
        completion["model_provider"] = "openai"
        completion["model"] = settings.graphrag_chat_model
        completion["api_base"] = "${GRAPHRAG_API_BASE}"
        completion["api_key"] = "${GRAPHRAG_API_KEY}"

        embedding = data["embedding_models"]["default_embedding_model"]
        embedding["model_provider"] = "openai"
        embedding["model"] = settings.graphrag_embedding_model
        embedding["api_base"] = "${GRAPHRAG_API_BASE}"
        embedding["api_key"] = "${GRAPHRAG_API_KEY}"
        embedding["call_args"] = {"encoding_format": "float"}

        data["input"]["type"] = "text"
        data["chunking"]["size"] = 1000
        data["chunking"]["overlap"] = 200
        data["vector_store"]["type"] = "lancedb"
        data["vector_store"]["db_uri"] = "output\\lancedb"
        data["vector_store"]["vector_size"] = settings.graphrag_vector_size
        data["extract_graph"]["entity_types"] = [
            "organization",
            "person",
            "geo",
            "event",
            "role",
            "page_module",
            "rule",
            "reward",
        ]
        data["snapshots"]["graphml"] = True

        settings_path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def _write_input_files(self, workspace: Path, documents: list[KnowledgeDocumentDetail]) -> None:
        input_dir = workspace / "input"
        input_dir.mkdir(parents=True, exist_ok=True)

        for document in documents:
            file_name = f"{self._safe_name(document.title)}-{document.id[:8]}.txt"
            content = "\n".join(
                [
                    f"Title: {document.title}",
                    f"Source: {document.source}",
                    f"SourceType: {document.source_type}",
                    f"Tags: {', '.join(document.tags)}",
                    f"URL: {document.url or ''}",
                    "",
                    document.content.strip(),
                ]
            )
            (input_dir / file_name).write_text(content, encoding="utf-8")

    def _run_command(
        self,
        command: list[str],
        *,
        env: dict[str, str],
        workspace: Path,
        stage: str,
    ) -> None:
        log_dir = workspace / "job-logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            command,
            env=env,
            cwd=settings.project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        (log_dir / f"{stage}.stdout.log").write_text(result.stdout or "", encoding="utf-8")
        (log_dir / f"{stage}.stderr.log").write_text(result.stderr or "", encoding="utf-8")

        if result.returncode != 0:
            tail = "\n".join(
                [line for line in (result.stderr or result.stdout).splitlines() if line.strip()][-20:]
            )
            msg = f"GraphRAG {stage} 失败。{tail or '请查看日志。'}"
            raise RuntimeError(msg)

    def _summarize_workspace(
        self,
        workspace: Path,
        method: str,
        documents: list[KnowledgeDocumentDetail],
    ) -> dict[str, Any]:
        output_dir = workspace / "output"
        stats_path = output_dir / "stats.json"
        artifact_counts = {
            "documents": self._count_parquet_rows(output_dir / "documents.parquet"),
            "text_units": self._count_parquet_rows(output_dir / "text_units.parquet"),
            "entities": self._count_parquet_rows(output_dir / "entities.parquet"),
            "relationships": self._count_parquet_rows(output_dir / "relationships.parquet"),
            "communities": self._count_parquet_rows(output_dir / "communities.parquet"),
            "community_reports": self._count_parquet_rows(output_dir / "community_reports.parquet"),
        }
        graphml_candidates = list(output_dir.glob("*.graphml"))
        return {
            "workspace_dir": str(workspace),
            "output_dir": str(output_dir),
            "method": method,
            "document_ids": [document.id for document in documents],
            "document_titles": [document.title for document in documents],
            "artifact_counts": artifact_counts,
            "stats": json.loads(stats_path.read_text(encoding="utf-8")) if stats_path.exists() else {},
            "graphml_path": str(graphml_candidates[0]) if graphml_candidates else None,
            "vector_store_dir": str((output_dir / "lancedb").resolve()),
            "logs_dir": str((workspace / "job-logs").resolve()),
        }

    def _archive_workspace(self, job_id: str, workspace: Path) -> str:
        output_dir = workspace / "output"
        archive_path = workspace / f"{job_id}-output.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in output_dir.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(workspace))

        object_key = f"graphrag/jobs/{job_id}/output.zip"
        object_storage_service.upload_bytes(
            object_key,
            archive_path.read_bytes(),
            "application/zip",
        )
        archive_path.unlink(missing_ok=True)
        return object_key

    def _count_parquet_rows(self, path: Path) -> int:
        if not path.exists():
            return 0
        return int(len(pd.read_parquet(path)))

    def _safe_name(self, value: str) -> str:
        normalized = "".join(char if char.isalnum() else "-" for char in value.strip().lower())
        return normalized.strip("-") or "document"


graphrag_service = GraphRAGService(settings.graphrag_workspace_dir)
