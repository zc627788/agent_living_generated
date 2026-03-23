"""知识库后台任务编排。

把耗时的批量重建和 GraphRAG 构图放到线程池执行，避免阻塞主 API 线程。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.core.config import settings
from app.db.database import database, utc_now
from app.models.schemas import KnowledgeDocumentDetail, KnowledgeJobDetail, KnowledgeJobSummary
from app.services.graphrag_service import graphrag_service
from app.services.knowledge_base import knowledge_base_service


class KnowledgeJobService:
    def __init__(self) -> None:
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="knowledge-jobs")

    def close(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)

    def list_jobs(self, limit: int = 20) -> list[KnowledgeJobSummary]:
        return database.list_jobs(limit=limit)

    def get_job(self, job_id: str) -> KnowledgeJobDetail | None:
        return database.get_job(job_id)

    def submit_reindex_job(self, document_ids: list[str]) -> KnowledgeJobDetail:
        """提交批量重建任务。"""
        normalized_ids = self._normalize_document_ids(document_ids)
        job = database.create_job(
            job_type="batch_reindex",
            provider=settings.rag_provider,
            document_ids=normalized_ids,
            progress_total=len(normalized_ids),
        )
        self.executor.submit(self._run_reindex_job, job.id, normalized_ids)
        return job

    def submit_graphrag_job(self, document_ids: list[str], method: str = "standard") -> KnowledgeJobDetail:
        """提交 GraphRAG 构图任务。"""
        normalized_ids = self._normalize_document_ids(document_ids)
        job = database.create_job(
            job_type=f"graphrag_{method}",
            provider="graphrag",
            document_ids=normalized_ids,
            progress_total=len(normalized_ids),
        )
        self.executor.submit(self._run_graphrag_job, job.id, normalized_ids, method)
        return job

    def _run_reindex_job(self, job_id: str, document_ids: list[str]) -> None:
        database.update_job(
            job_id,
            status="running",
            started_at=utc_now(),
            progress_current=0,
            progress_total=len(document_ids),
            error_message="",
        )
        try:
            documents, chunks = knowledge_base_service.reindex_documents(document_ids)
            database.update_job(
                job_id,
                status="succeeded",
                progress_current=len(document_ids),
                progress_total=len(document_ids),
                finished_at=utc_now(),
                result={
                    "documents": documents,
                    "chunks": chunks,
                    "document_ids": document_ids,
                },
            )
        except Exception as error:
            database.update_job(
                job_id,
                status="failed",
                finished_at=utc_now(),
                error_message=str(error),
                result={"document_ids": document_ids},
            )

    def _run_graphrag_job(self, job_id: str, document_ids: list[str], method: str) -> None:
        database.update_job(
            job_id,
            status="running",
            started_at=utc_now(),
            progress_current=0,
            progress_total=len(document_ids),
            error_message="",
        )
        try:
            documents = self._load_documents(document_ids)
            result = graphrag_service.build_index(job_id=job_id, documents=documents, method=method)
            database.update_job(
                job_id,
                status="succeeded",
                progress_current=len(document_ids),
                progress_total=len(document_ids),
                finished_at=utc_now(),
                result=result,
            )
        except Exception as error:
            database.update_job(
                job_id,
                status="failed",
                finished_at=utc_now(),
                error_message=str(error),
                result={"document_ids": document_ids, "method": method},
            )

    def _normalize_document_ids(self, document_ids: list[str]) -> list[str]:
        if document_ids:
            return document_ids
        return [document.id for document in database.list_documents()]

    def _load_documents(self, document_ids: list[str]) -> list[KnowledgeDocumentDetail]:
        documents: list[KnowledgeDocumentDetail] = []
        for document_id in document_ids:
            document = knowledge_base_service.get_document(document_id)
            if document is None:
                msg = f"文档 {document_id} 不存在。"
                raise ValueError(msg)
            documents.append(document)
        return documents


knowledge_job_service = KnowledgeJobService()
