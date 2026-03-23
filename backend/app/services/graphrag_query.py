"""GraphRAG 查询服务。

职责是读取已构建完成的 GraphRAG 产物，并将实体、关系、社区报告整理成前端能直接消费的结果。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from app.db.database import database
from app.models.schemas import (
    GraphCommunityReport,
    GraphEdge,
    GraphIndexSummary,
    GraphNode,
    GraphQueryResponse,
)
from app.services.llm_service import llm_service
from app.services.retriever import tokenize


class GraphRAGQueryService:
    def list_indexes(self, limit: int = 10) -> list[GraphIndexSummary]:
        """列出最近成功完成的 GraphRAG 索引任务。"""
        jobs = database.list_job_details(limit=limit * 2, provider="graphrag", status="succeeded")
        indexes: list[GraphIndexSummary] = []
        for job in jobs:
            result = job.result or {}
            indexes.append(
                GraphIndexSummary(
                    job_id=job.id,
                    method=str(result.get("method", job.job_type.removeprefix("graphrag_"))),
                    created_at=job.created_at,
                    document_ids=list(result.get("document_ids", [])),
                    document_titles=list(result.get("document_titles", [])),
                    artifact_counts={
                        key: int(value)
                        for key, value in dict(result.get("artifact_counts", {})).items()
                    },
                    workspace_dir=result.get("workspace_dir"),
                    graphml_path=result.get("graphml_path"),
                )
            )
            if len(indexes) >= limit:
                break
        return indexes

    def query(
        self,
        *,
        job_id: str,
        query: str,
        mode: str = "local",
        entity_limit: int = 12,
        edge_limit: int = 20,
        community_limit: int = 3,
    ) -> GraphQueryResponse:
        job = database.get_job(job_id)
        if job is None or job.provider != "graphrag" or job.status != "succeeded":
            raise ValueError("GraphRAG 查询索引不存在或尚未构建完成。")

        result = job.result or {}
        output_dir = result.get("output_dir")
        if not output_dir:
            raise ValueError("GraphRAG 任务缺少输出目录。")

        frames = self._load_frames(Path(str(output_dir)).resolve())
        rewritten_query = llm_service.rewrite_query(query, "graph")
        tokens = tokenize(rewritten_query or query)

        entity_rows = self._rank_entities(frames["entities"], tokens).head(entity_limit)
        entity_titles = set(entity_rows["title"].tolist())

        relationship_rows = self._rank_relationships(frames["relationships"], tokens, entity_titles).head(edge_limit)
        entity_titles.update(relationship_rows["source"].tolist())
        entity_titles.update(relationship_rows["target"].tolist())

        selected_entities = frames["entities"][frames["entities"]["title"].isin(entity_titles)].copy()
        selected_entities = selected_entities.sort_values(["degree", "frequency"], ascending=False).head(entity_limit)
        entity_titles = set(selected_entities["title"].tolist())

        selected_relationships = relationship_rows[
            relationship_rows["source"].isin(entity_titles) & relationship_rows["target"].isin(entity_titles)
        ].head(edge_limit)

        report_rows = self._rank_reports(
            frames["community_reports"],
            tokens=tokens,
            entity_titles=entity_titles,
        ).head(community_limit)

        nodes = [
            GraphNode(
                id=str(row["title"]),
                label=str(row["title"]),
                kind=str(row.get("type", "ENTITY")).lower(),
                size=max(1.0, min(10.0, float(row.get("degree", 1)) / 2)),
                score=float(row.get("query_score", 0.0)),
                community=None,
                description=str(row.get("description", "")) or None,
            )
            for _, row in selected_entities.iterrows()
        ]

        edges = [
            GraphEdge(
                source=str(row["source"]),
                target=str(row["target"]),
                weight=float(row.get("weight", 1.0)),
                label=str(row.get("description", ""))[:120] or None,
            )
            for _, row in selected_relationships.iterrows()
        ]

        reports = [
            GraphCommunityReport(
                id=str(row["id"]),
                title=str(row["title"]),
                summary=str(row["summary"]),
                rank=float(row.get("query_score", row.get("rank", 0.0))),
            )
            for _, row in report_rows.iterrows()
        ]

        fallback = self._build_fallback_answer(query, selected_entities, report_rows, mode)
        answer = llm_service.summarize_graph_query(
            query=query,
            rewritten_query=rewritten_query,
            entities=selected_entities[
                ["title", "type", "description", "degree", "query_score"]
            ].to_dict(orient="records"),
            reports=report_rows[["title", "summary", "rank"]].to_dict(orient="records"),
            fallback=fallback,
        )

        return GraphQueryResponse(
            answer=answer,
            rewritten_query=rewritten_query,
            nodes=nodes,
            edges=edges,
            reports=reports,
            artifacts={
                key: int(value)
                for key, value in dict(result.get("artifact_counts", {})).items()
            },
        )

    @lru_cache(maxsize=12)
    def _load_frames(self, output_dir: Path) -> dict[str, pd.DataFrame]:
        # GraphRAG 产物是 parquet，做缓存能显著降低重复查询的 I/O 成本。
        return {
            "entities": pd.read_parquet(output_dir / "entities.parquet"),
            "relationships": pd.read_parquet(output_dir / "relationships.parquet"),
            "community_reports": pd.read_parquet(output_dir / "community_reports.parquet"),
        }

    def _rank_entities(self, frame: pd.DataFrame, tokens: list[str]) -> pd.DataFrame:
        ranked = frame.copy()
        ranked["query_score"] = ranked.apply(
            lambda row: self._text_score(
                tokens,
                [str(row.get("title", "")), str(row.get("description", ""))],
                base=float(row.get("degree", 0)) * 0.02,
            ),
            axis=1,
        )
        return ranked.sort_values("query_score", ascending=False)

    def _rank_relationships(
        self,
        frame: pd.DataFrame,
        tokens: list[str],
        entity_titles: set[str],
    ) -> pd.DataFrame:
        ranked = frame.copy()
        ranked["query_score"] = ranked.apply(
            lambda row: self._text_score(
                tokens,
                [
                    str(row.get("source", "")),
                    str(row.get("target", "")),
                    str(row.get("description", "")),
                ],
                base=float(row.get("weight", 0)) * 0.03,
            )
            + (
                0.2
                if entity_titles
                and (
                    str(row.get("source", "")) in entity_titles
                    or str(row.get("target", "")) in entity_titles
                )
                else 0.0
            ),
            axis=1,
        )
        return ranked.sort_values("query_score", ascending=False)

    def _rank_reports(
        self,
        frame: pd.DataFrame,
        *,
        tokens: list[str],
        entity_titles: set[str],
    ) -> pd.DataFrame:
        ranked = frame.copy()
        ranked["query_score"] = ranked.apply(
            lambda row: self._text_score(
                tokens,
                [str(row.get("title", "")), str(row.get("summary", "")), str(row.get("full_content", ""))],
                base=float(row.get("rank", 0)) * 0.05,
            )
            + sum(0.08 for title in entity_titles if title.lower() in str(row.get("full_content", "")).lower()),
            axis=1,
        )
        return ranked.sort_values("query_score", ascending=False)

    def _text_score(self, tokens: list[str], texts: list[str], *, base: float = 0.0) -> float:
        lowered = " ".join(texts).lower()
        if not tokens:
            return base
        hits = sum(1 for token in set(tokens) if token in lowered)
        return base + hits * 0.16

    def _build_fallback_answer(
        self,
        query: str,
        entities: pd.DataFrame,
        reports: pd.DataFrame,
        mode: str,
    ) -> str:
        if entities.empty and reports.empty:
            return f"当前图谱中没有找到与“{query}”强相关的实体或社区。"

        entity_names = "、".join(entities["title"].head(5).tolist()) or "暂无显著实体"
        report_title = reports.iloc[0]["title"] if not reports.empty else "暂无社区摘要"
        if mode == "global":
            return f"全局视角下，最相关的社区是“{report_title}”，关键实体包括：{entity_names}。"
        return f"局部视角下，最相关的实体包括：{entity_names}。最相关社区摘要为“{report_title}”。"


graphrag_query_service = GraphRAGQueryService()
