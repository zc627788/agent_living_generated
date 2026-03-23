"""数据库访问层。

这里不引入复杂 ORM 实体，而是直接用 SQLAlchemy Core 封装仓储操作，便于在 SQLite 和 PostgreSQL 间切换。
"""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, RowMapping

from app.core.config import settings
from app.models.schemas import (
    KnowledgeChunkPreview,
    KnowledgeDocumentDetail,
    KnowledgeDocumentSummary,
    KnowledgeDocumentVersionDetail,
    KnowledgeDocumentVersionSummary,
    KnowledgeJobDetail,
    KnowledgeJobSummary,
    Message,
    ReferenceCard,
    SessionSummary,
    SessionState,
)

SESSION_TABLE = "prd_agent_sessions"
MESSAGE_TABLE = "prd_agent_messages"
DOCUMENT_TABLE = "prd_agent_knowledge_documents"
CHUNK_TABLE = "prd_agent_knowledge_chunks"
VERSION_TABLE = "prd_agent_knowledge_document_versions"
JOB_TABLE = "prd_agent_knowledge_jobs"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self.engine: Engine = create_engine(
            database_url,
            future=True,
            pool_pre_ping=True,
            connect_args=connect_args,
        )

    @contextmanager
    def connection(self) -> Iterator[Connection]:
        with self.engine.begin() as connection:
            yield connection

    def close(self) -> None:
        self.engine.dispose()

    def initialize(self) -> None:
        # 所有业务表都在初始化阶段显式创建，MVP 环境无需额外迁移脚本即可跑通。
        with self.connection() as conn:
            conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {SESSION_TABLE} (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        topic_type TEXT NOT NULL,
                        slots_json TEXT NOT NULL,
                        missing_slots_json TEXT NOT NULL,
                        risk_alerts_json TEXT NOT NULL,
                        references_json TEXT NOT NULL,
                        prd_markdown TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {MESSAGE_TABLE} (
                        id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {DOCUMENT_TABLE} (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        source_type TEXT NOT NULL,
                        source TEXT NOT NULL,
                        url TEXT,
                        thumbnail_url TEXT,
                        tags_json TEXT NOT NULL,
                        content TEXT NOT NULL,
                        storage_key TEXT,
                        origin_file_name TEXT,
                        is_builtin INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {CHUNK_TABLE} (
                        id TEXT PRIMARY KEY,
                        document_id TEXT NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        section_path TEXT NOT NULL,
                        content TEXT NOT NULL,
                        prev_chunk_id TEXT,
                        next_chunk_id TEXT,
                        tags_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {VERSION_TABLE} (
                        id TEXT PRIMARY KEY,
                        document_id TEXT NOT NULL,
                        version_number INTEGER NOT NULL,
                        title TEXT NOT NULL,
                        source_type TEXT NOT NULL,
                        source TEXT NOT NULL,
                        url TEXT,
                        thumbnail_url TEXT,
                        tags_json TEXT NOT NULL,
                        content TEXT NOT NULL,
                        storage_key TEXT,
                        origin_file_name TEXT,
                        change_summary TEXT,
                        created_at TEXT NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {JOB_TABLE} (
                        id TEXT PRIMARY KEY,
                        job_type TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        status TEXT NOT NULL,
                        document_ids_json TEXT NOT NULL,
                        progress_current INTEGER NOT NULL DEFAULT 0,
                        progress_total INTEGER NOT NULL DEFAULT 0,
                        error_message TEXT,
                        result_json TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        started_at TEXT,
                        finished_at TEXT
                    )
                    """
                )
            )

    def reset_knowledge(self) -> None:
        with self.connection() as conn:
            conn.execute(text(f"DELETE FROM {CHUNK_TABLE}"))

    def delete_chunks_for_documents(self, document_ids: list[str] | None = None) -> None:
        with self.connection() as conn:
            if document_ids:
                for document_id in document_ids:
                    conn.execute(
                        text(f"DELETE FROM {CHUNK_TABLE} WHERE document_id = :document_id"),
                        {"document_id": document_id},
                    )
            else:
                conn.execute(text(f"DELETE FROM {CHUNK_TABLE}"))

    def knowledge_counts(self) -> tuple[int, int]:
        with self.connection() as conn:
            docs = conn.execute(text(f"SELECT COUNT(*) AS count FROM {DOCUMENT_TABLE}")).mappings().one()["count"]
            chunks = conn.execute(text(f"SELECT COUNT(*) AS count FROM {CHUNK_TABLE}")).mappings().one()["count"]
            return int(docs), int(chunks)

    def upsert_builtin_document(
        self,
        *,
        title: str,
        source_type: str,
        source: str,
        url: str | None,
        thumbnail_url: str | None,
        tags: list[str],
        content: str,
        storage_key: str,
    ) -> str:
        with self.connection() as conn:
            existing = conn.execute(
                text(f"SELECT id FROM {DOCUMENT_TABLE} WHERE storage_key = :storage_key"),
                {"storage_key": storage_key},
            ).mappings().first()
            now = utc_now()
            if existing:
                conn.execute(
                    text(
                        f"""
                        UPDATE {DOCUMENT_TABLE}
                        SET title = :title,
                            source_type = :source_type,
                            source = :source,
                            url = :url,
                            thumbnail_url = :thumbnail_url,
                            tags_json = :tags_json,
                            content = :content,
                            is_builtin = 1,
                            updated_at = :updated_at
                        WHERE id = :id
                        """
                    ),
                    {
                        "id": existing["id"],
                        "title": title,
                        "source_type": source_type,
                        "source": source,
                        "url": url,
                        "thumbnail_url": thumbnail_url,
                        "tags_json": json.dumps(tags, ensure_ascii=False),
                        "content": content,
                        "updated_at": now,
                    },
                )
                return str(existing["id"])

            document_id = str(uuid.uuid4())
            conn.execute(
                text(
                    f"""
                    INSERT INTO {DOCUMENT_TABLE} (
                        id, title, source_type, source, url, thumbnail_url, tags_json, content,
                        storage_key, origin_file_name, is_builtin, created_at, updated_at
                    )
                    VALUES (
                        :id, :title, :source_type, :source, :url, :thumbnail_url, :tags_json, :content,
                        :storage_key, :origin_file_name, :is_builtin, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": document_id,
                    "title": title,
                    "source_type": source_type,
                    "source": source,
                    "url": url,
                    "thumbnail_url": thumbnail_url,
                    "tags_json": json.dumps(tags, ensure_ascii=False),
                    "content": content,
                    "storage_key": storage_key,
                    "origin_file_name": None,
                    "is_builtin": 1,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            return document_id

    def create_document(
        self,
        *,
        title: str,
        source_type: str,
        source: str,
        url: str | None,
        thumbnail_url: str | None,
        tags: list[str],
        content: str,
        storage_key: str | None,
        origin_file_name: str | None,
        is_builtin: bool = False,
    ) -> str:
        document_id = str(uuid.uuid4())
        now = utc_now()
        with self.connection() as conn:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {DOCUMENT_TABLE} (
                        id, title, source_type, source, url, thumbnail_url, tags_json, content,
                        storage_key, origin_file_name, is_builtin, created_at, updated_at
                    )
                    VALUES (
                        :id, :title, :source_type, :source, :url, :thumbnail_url, :tags_json, :content,
                        :storage_key, :origin_file_name, :is_builtin, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": document_id,
                    "title": title,
                    "source_type": source_type,
                    "source": source,
                    "url": url,
                    "thumbnail_url": thumbnail_url,
                    "tags_json": json.dumps(tags, ensure_ascii=False),
                    "content": content,
                    "storage_key": storage_key,
                    "origin_file_name": origin_file_name,
                    "is_builtin": 1 if is_builtin else 0,
                    "created_at": now,
                    "updated_at": now,
                },
            )
        return document_id

    def update_document(
        self,
        document_id: str,
        *,
        title: str,
        source_type: str,
        source: str,
        url: str | None,
        thumbnail_url: str | None,
        tags: list[str],
        content: str,
        storage_key: str | None = None,
        origin_file_name: str | None = None,
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                text(
                    f"""
                    UPDATE {DOCUMENT_TABLE}
                    SET title = :title,
                        source_type = :source_type,
                        source = :source,
                        url = :url,
                        thumbnail_url = :thumbnail_url,
                        tags_json = :tags_json,
                        content = :content,
                        storage_key = COALESCE(:storage_key, storage_key),
                        origin_file_name = COALESCE(:origin_file_name, origin_file_name),
                        updated_at = :updated_at
                    WHERE id = :id
                    """
                ),
                {
                    "id": document_id,
                    "title": title,
                    "source_type": source_type,
                    "source": source,
                    "url": url,
                    "thumbnail_url": thumbnail_url,
                    "tags_json": json.dumps(tags, ensure_ascii=False),
                    "content": content,
                    "storage_key": storage_key,
                    "origin_file_name": origin_file_name,
                    "updated_at": utc_now(),
                },
            )

    def delete_document(self, document_id: str) -> None:
        with self.connection() as conn:
            conn.execute(text(f"DELETE FROM {CHUNK_TABLE} WHERE document_id = :document_id"), {"document_id": document_id})
            conn.execute(text(f"DELETE FROM {DOCUMENT_TABLE} WHERE id = :document_id"), {"document_id": document_id})

    def create_document_version_snapshot(self, document_id: str, change_summary: str | None = None) -> str:
        with self.connection() as conn:
            row = conn.execute(
                text(f"SELECT * FROM {DOCUMENT_TABLE} WHERE id = :document_id"),
                {"document_id": document_id},
            ).mappings().first()
            if row is None:
                msg = f"Document {document_id} not found."
                raise ValueError(msg)

            version_number = conn.execute(
                text(
                    f"""
                    SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version
                    FROM {VERSION_TABLE}
                    WHERE document_id = :document_id
                    """
                ),
                {"document_id": document_id},
            ).mappings().one()["next_version"]

            version_id = str(uuid.uuid4())
            conn.execute(
                text(
                    f"""
                    INSERT INTO {VERSION_TABLE} (
                        id, document_id, version_number, title, source_type, source, url, thumbnail_url,
                        tags_json, content, storage_key, origin_file_name, change_summary, created_at
                    )
                    VALUES (
                        :id, :document_id, :version_number, :title, :source_type, :source, :url, :thumbnail_url,
                        :tags_json, :content, :storage_key, :origin_file_name, :change_summary, :created_at
                    )
                    """
                ),
                {
                    "id": version_id,
                    "document_id": document_id,
                    "version_number": int(version_number),
                    "title": row["title"],
                    "source_type": row["source_type"],
                    "source": row["source"],
                    "url": row["url"],
                    "thumbnail_url": row["thumbnail_url"],
                    "tags_json": row["tags_json"],
                    "content": row["content"],
                    "storage_key": row["storage_key"],
                    "origin_file_name": row["origin_file_name"],
                    "change_summary": change_summary,
                    "created_at": utc_now(),
                },
            )
        return version_id

    def list_document_versions(self, document_id: str) -> list[KnowledgeDocumentVersionSummary]:
        with self.connection() as conn:
            rows = conn.execute(
                text(
                    f"""
                    SELECT id, document_id, version_number, title, source_type, source, tags_json, change_summary, created_at
                    FROM {VERSION_TABLE}
                    WHERE document_id = :document_id
                    ORDER BY version_number DESC
                    """
                ),
                {"document_id": document_id},
            ).mappings().all()
        return [self._row_to_document_version_summary(row) for row in rows]

    def get_document_version(self, version_id: str) -> KnowledgeDocumentVersionDetail | None:
        with self.connection() as conn:
            row = conn.execute(
                text(f"SELECT * FROM {VERSION_TABLE} WHERE id = :version_id"),
                {"version_id": version_id},
            ).mappings().first()
        if row is None:
            return None
        return self._row_to_document_version_detail(row)

    def create_job(
        self,
        *,
        job_type: str,
        provider: str,
        document_ids: list[str],
        progress_total: int = 0,
    ) -> KnowledgeJobDetail:
        job_id = str(uuid.uuid4())
        now = utc_now()
        with self.connection() as conn:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {JOB_TABLE} (
                        id, job_type, provider, status, document_ids_json, progress_current, progress_total,
                        error_message, result_json, created_at, updated_at, started_at, finished_at
                    )
                    VALUES (
                        :id, :job_type, :provider, :status, :document_ids_json, :progress_current, :progress_total,
                        :error_message, :result_json, :created_at, :updated_at, :started_at, :finished_at
                    )
                    """
                ),
                {
                    "id": job_id,
                    "job_type": job_type,
                    "provider": provider,
                    "status": "pending",
                    "document_ids_json": json.dumps(document_ids, ensure_ascii=False),
                    "progress_current": 0,
                    "progress_total": progress_total,
                    "error_message": None,
                    "result_json": None,
                    "created_at": now,
                    "updated_at": now,
                    "started_at": None,
                    "finished_at": None,
                },
            )
        job = self.get_job(job_id)
        if job is None:
            msg = f"Job {job_id} creation failed."
            raise ValueError(msg)
        return job

    def update_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        progress_current: int | None = None,
        progress_total: int | None = None,
        error_message: str | None = None,
        result: dict[str, Any] | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> None:
        updates = ["updated_at = :updated_at"]
        params: dict[str, Any] = {"id": job_id, "updated_at": utc_now()}
        if status is not None:
            updates.append("status = :status")
            params["status"] = status
        if progress_current is not None:
            updates.append("progress_current = :progress_current")
            params["progress_current"] = progress_current
        if progress_total is not None:
            updates.append("progress_total = :progress_total")
            params["progress_total"] = progress_total
        if error_message is not None:
            updates.append("error_message = :error_message")
            params["error_message"] = error_message
        if result is not None:
            updates.append("result_json = :result_json")
            params["result_json"] = json.dumps(result, ensure_ascii=False)
        if started_at is not None:
            updates.append("started_at = :started_at")
            params["started_at"] = started_at
        if finished_at is not None:
            updates.append("finished_at = :finished_at")
            params["finished_at"] = finished_at

        with self.connection() as conn:
            conn.execute(
                text(f"UPDATE {JOB_TABLE} SET {', '.join(updates)} WHERE id = :id"),
                params,
            )

    def list_jobs(self, limit: int = 20) -> list[KnowledgeJobSummary]:
        with self.connection() as conn:
            rows = conn.execute(
                text(
                    f"""
                    SELECT *
                    FROM {JOB_TABLE}
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            ).mappings().all()
        return [self._row_to_job_summary(row) for row in rows]

    def list_job_details(
        self,
        *,
        limit: int = 20,
        provider: str | None = None,
        status: str | None = None,
    ) -> list[KnowledgeJobDetail]:
        query = f"SELECT * FROM {JOB_TABLE}"
        clauses: list[str] = []
        params: dict[str, Any] = {"limit": limit}
        if provider:
            clauses.append("provider = :provider")
            params["provider"] = provider
        if status:
            clauses.append("status = :status")
            params["status"] = status
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC LIMIT :limit"

        with self.connection() as conn:
            rows = conn.execute(text(query), params).mappings().all()
        return [self._row_to_job_detail(row) for row in rows]

    def get_job(self, job_id: str) -> KnowledgeJobDetail | None:
        with self.connection() as conn:
            row = conn.execute(
                text(f"SELECT * FROM {JOB_TABLE} WHERE id = :job_id"),
                {"job_id": job_id},
            ).mappings().first()
        if row is None:
            return None
        return self._row_to_job_detail(row)

    def get_document(self, document_id: str) -> KnowledgeDocumentDetail | None:
        with self.connection() as conn:
            row = conn.execute(
                text(
                    f"""
                    SELECT
                        kd.*,
                        COUNT(kc.id) AS chunk_count
                    FROM {DOCUMENT_TABLE} kd
                    LEFT JOIN {CHUNK_TABLE} kc ON kc.document_id = kd.id
                    WHERE kd.id = :document_id
                    GROUP BY kd.id
                    """
                ),
                {"document_id": document_id},
            ).mappings().first()
        if row is None:
            return None
        return self._row_to_document_detail(row)

    def list_documents(self) -> list[KnowledgeDocumentSummary]:
        with self.connection() as conn:
            rows = conn.execute(
                text(
                    f"""
                    SELECT
                        kd.id,
                        kd.title,
                        kd.source_type,
                        kd.source,
                        kd.url,
                        kd.thumbnail_url,
                        kd.tags_json,
                        kd.created_at,
                        kd.updated_at,
                        kd.is_builtin,
                        COUNT(kc.id) AS chunk_count
                    FROM {DOCUMENT_TABLE} kd
                    LEFT JOIN {CHUNK_TABLE} kc ON kc.document_id = kd.id
                    GROUP BY kd.id
                    ORDER BY kd.updated_at DESC
                    """
                )
            ).mappings().all()
        return [self._row_to_document_summary(row) for row in rows]

    def list_document_records(self, document_ids: list[str] | None = None) -> list[dict[str, Any]]:
        with self.connection() as conn:
            if document_ids:
                rows = []
                for document_id in document_ids:
                    row = conn.execute(
                        text(f"SELECT * FROM {DOCUMENT_TABLE} WHERE id = :document_id"),
                        {"document_id": document_id},
                    ).mappings().first()
                    if row:
                        rows.append(row)
            else:
                rows = conn.execute(text(f"SELECT * FROM {DOCUMENT_TABLE} ORDER BY updated_at DESC")).mappings().all()
        return [dict(row) for row in rows]

    def insert_chunk(
        self,
        *,
        chunk_id: str,
        document_id: str,
        chunk_index: int,
        section_path: str,
        content: str,
        prev_chunk_id: str | None,
        next_chunk_id: str | None,
        tags: list[str],
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {CHUNK_TABLE} (
                        id, document_id, chunk_index, section_path, content, prev_chunk_id, next_chunk_id, tags_json, created_at
                    )
                    VALUES (
                        :id, :document_id, :chunk_index, :section_path, :content, :prev_chunk_id, :next_chunk_id, :tags_json, :created_at
                    )
                    """
                ),
                {
                    "id": chunk_id,
                    "document_id": document_id,
                    "chunk_index": chunk_index,
                    "section_path": section_path,
                    "content": content,
                    "prev_chunk_id": prev_chunk_id,
                    "next_chunk_id": next_chunk_id,
                    "tags_json": json.dumps(tags, ensure_ascii=False),
                    "created_at": utc_now(),
                },
            )

    def list_chunks(self, document_id: str | None = None) -> list[KnowledgeChunkPreview]:
        query = f"""
            SELECT kc.id, kc.document_id, kc.chunk_index, kc.section_path, kc.content, kc.tags_json, kd.title
            FROM {CHUNK_TABLE} kc
            INNER JOIN {DOCUMENT_TABLE} kd ON kd.id = kc.document_id
        """
        params: dict[str, Any] = {}
        if document_id:
            query += " WHERE kc.document_id = :document_id"
            params["document_id"] = document_id
        query += " ORDER BY kd.title ASC, kc.chunk_index ASC"

        with self.connection() as conn:
            rows = conn.execute(text(query), params).mappings().all()
        return [
            KnowledgeChunkPreview(
                id=str(row["id"]),
                document_id=str(row["document_id"]),
                title=str(row["title"]),
                section_path=str(row["section_path"]),
                content=str(row["content"]),
                tags=json.loads(row["tags_json"]),
                chunk_index=int(row["chunk_index"]),
            )
            for row in rows
        ]

    def get_chunk_context(self, chunk_id: str, neighbor_hops: int = 1) -> dict[str, Any] | None:
        # 命中切片后顺带回补前后邻接块，保证 RAG 上下文连贯。
        with self.connection() as conn:
            row = conn.execute(
                text(
                    f"""
                    SELECT kc.*, kd.title, kd.source, kd.source_type, kd.url, kd.thumbnail_url
                    FROM {CHUNK_TABLE} kc
                    INNER JOIN {DOCUMENT_TABLE} kd ON kd.id = kc.document_id
                    WHERE kc.id = :chunk_id
                    """
                ),
                {"chunk_id": chunk_id},
            ).mappings().first()

            if row is None:
                return None

            document_id = str(row["document_id"])
            center_index = int(row["chunk_index"])
            start_index = max(0, center_index - neighbor_hops)
            end_index = center_index + neighbor_hops
            neighbors = conn.execute(
                text(
                    f"""
                    SELECT id, chunk_index, section_path, content
                    FROM {CHUNK_TABLE}
                    WHERE document_id = :document_id
                      AND chunk_index BETWEEN :start_index AND :end_index
                    ORDER BY chunk_index ASC
                    """
                ),
                {
                    "document_id": document_id,
                    "start_index": start_index,
                    "end_index": end_index,
                },
            ).mappings().all()

        return {
            "id": str(row["id"]),
            "document_id": document_id,
            "title": str(row["title"]),
            "source": str(row["source"]),
            "source_type": str(row["source_type"]),
            "url": row["url"],
            "thumbnail_url": row["thumbnail_url"],
            "section_path": str(row["section_path"]),
            "chunk_index": center_index,
            "content": str(row["content"]),
            "combined_content": "\n".join(str(item["content"]) for item in neighbors).strip(),
            "neighbor_ids": [str(item["id"]) for item in neighbors],
        }

    def create_session(
        self,
        title: str,
        topic_type: str,
        slots: dict[str, str],
        missing_slots: list[str],
        risk_alerts: list[str],
        references: list[ReferenceCard],
        prd_markdown: str,
    ) -> str:
        session_id = str(uuid.uuid4())
        now = utc_now()
        with self.connection() as conn:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {SESSION_TABLE} (
                        id, title, topic_type, slots_json, missing_slots_json, risk_alerts_json, references_json,
                        prd_markdown, created_at, updated_at
                    )
                    VALUES (
                        :id, :title, :topic_type, :slots_json, :missing_slots_json, :risk_alerts_json, :references_json,
                        :prd_markdown, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": session_id,
                    "title": title,
                    "topic_type": topic_type,
                    "slots_json": json.dumps(slots, ensure_ascii=False),
                    "missing_slots_json": json.dumps(missing_slots, ensure_ascii=False),
                    "risk_alerts_json": json.dumps(risk_alerts, ensure_ascii=False),
                    "references_json": json.dumps([reference.model_dump() for reference in references], ensure_ascii=False),
                    "prd_markdown": prd_markdown,
                    "created_at": now,
                    "updated_at": now,
                },
            )
        return session_id

    def update_session(
        self,
        session_id: str,
        title: str,
        topic_type: str,
        slots: dict[str, str],
        missing_slots: list[str],
        risk_alerts: list[str],
        references: list[ReferenceCard],
        prd_markdown: str,
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                text(
                    f"""
                    UPDATE {SESSION_TABLE}
                    SET title = :title,
                        topic_type = :topic_type,
                        slots_json = :slots_json,
                        missing_slots_json = :missing_slots_json,
                        risk_alerts_json = :risk_alerts_json,
                        references_json = :references_json,
                        prd_markdown = :prd_markdown,
                        updated_at = :updated_at
                    WHERE id = :id
                    """
                ),
                {
                    "id": session_id,
                    "title": title,
                    "topic_type": topic_type,
                    "slots_json": json.dumps(slots, ensure_ascii=False),
                    "missing_slots_json": json.dumps(missing_slots, ensure_ascii=False),
                    "risk_alerts_json": json.dumps(risk_alerts, ensure_ascii=False),
                    "references_json": json.dumps([reference.model_dump() for reference in references], ensure_ascii=False),
                    "prd_markdown": prd_markdown,
                    "updated_at": utc_now(),
                },
            )

    def create_message(self, session_id: str, role: str, content: str) -> Message:
        message = Message(
            id=str(uuid.uuid4()),
            role=role,  # type: ignore[arg-type]
            content=content,
            created_at=datetime.now(timezone.utc),
        )
        with self.connection() as conn:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {MESSAGE_TABLE} (id, session_id, role, content, created_at)
                    VALUES (:id, :session_id, :role, :content, :created_at)
                    """
                ),
                {
                    "id": message.id,
                    "session_id": session_id,
                    "role": message.role,
                    "content": message.content,
                    "created_at": message.created_at.isoformat(),
                },
            )
        return message

    def list_messages(self, session_id: str) -> list[Message]:
        with self.connection() as conn:
            rows = conn.execute(
                text(
                    f"""
                    SELECT id, role, content, created_at
                    FROM {MESSAGE_TABLE}
                    WHERE session_id = :session_id
                    ORDER BY created_at ASC
                    """
                ),
                {"session_id": session_id},
            ).mappings().all()
        return [self._row_to_message(row) for row in rows]

    def get_session(self, session_id: str) -> SessionState | None:
        with self.connection() as conn:
            row = conn.execute(
                text(f"SELECT * FROM {SESSION_TABLE} WHERE id = :session_id"),
                {"session_id": session_id},
            ).mappings().first()
        if row is None:
            return None
        return self._row_to_session(row)

    def list_sessions(self, limit: int = 50) -> list[SessionSummary]:
        with self.connection() as conn:
            rows = conn.execute(
                text(
                    f"""
                    SELECT
                        s.id,
                        s.title,
                        s.topic_type,
                        s.created_at,
                        s.updated_at,
                        COUNT(m.id) AS message_count,
                        COALESCE(
                            (
                                SELECT content
                                FROM {MESSAGE_TABLE} lm
                                WHERE lm.session_id = s.id
                                ORDER BY lm.created_at DESC
                                LIMIT 1
                            ),
                            ''
                        ) AS last_message_preview
                    FROM {SESSION_TABLE} s
                    LEFT JOIN {MESSAGE_TABLE} m ON m.session_id = s.id
                    GROUP BY s.id
                    ORDER BY s.updated_at DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            ).mappings().all()
        return [self._row_to_session_summary(row) for row in rows]

    def update_session_title(self, session_id: str, title: str) -> None:
        with self.connection() as conn:
            conn.execute(
                text(
                    f"""
                    UPDATE {SESSION_TABLE}
                    SET title = :title,
                        updated_at = :updated_at
                    WHERE id = :id
                    """
                ),
                {
                    "id": session_id,
                    "title": title,
                    "updated_at": utc_now(),
                },
            )

    def delete_session(self, session_id: str) -> None:
        with self.connection() as conn:
            conn.execute(
                text(f"DELETE FROM {MESSAGE_TABLE} WHERE session_id = :session_id"),
                {"session_id": session_id},
            )
            conn.execute(
                text(f"DELETE FROM {SESSION_TABLE} WHERE id = :session_id"),
                {"session_id": session_id},
            )

    def _row_to_message(self, row: RowMapping) -> Message:
        return Message(
            id=str(row["id"]),
            role=str(row["role"]),
            content=str(row["content"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
        )

    def _row_to_document_summary(self, row: RowMapping) -> KnowledgeDocumentSummary:
        return KnowledgeDocumentSummary(
            id=str(row["id"]),
            title=str(row["title"]),
            source_type=str(row["source_type"]),
            source=str(row["source"]),
            url=row["url"],
            thumbnail_url=row["thumbnail_url"],
            tags=json.loads(row["tags_json"]),
            chunk_count=int(row["chunk_count"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
            is_builtin=bool(row["is_builtin"]),
        )

    def _row_to_document_detail(self, row: RowMapping) -> KnowledgeDocumentDetail:
        summary = self._row_to_document_summary(row)
        return KnowledgeDocumentDetail(
            **summary.model_dump(),
            content=str(row["content"]),
            origin_file_name=row["origin_file_name"],
            storage_key=row["storage_key"],
        )

    def _row_to_document_version_summary(self, row: RowMapping) -> KnowledgeDocumentVersionSummary:
        return KnowledgeDocumentVersionSummary(
            id=str(row["id"]),
            document_id=str(row["document_id"]),
            version_number=int(row["version_number"]),
            title=str(row["title"]),
            source_type=str(row["source_type"]),
            source=str(row["source"]),
            tags=json.loads(row["tags_json"]),
            change_summary=row["change_summary"],
            created_at=datetime.fromisoformat(str(row["created_at"])),
        )

    def _row_to_document_version_detail(self, row: RowMapping) -> KnowledgeDocumentVersionDetail:
        summary = self._row_to_document_version_summary(row)
        return KnowledgeDocumentVersionDetail(
            **summary.model_dump(),
            url=row["url"],
            thumbnail_url=row["thumbnail_url"],
            content=str(row["content"]),
            origin_file_name=row["origin_file_name"],
            storage_key=row["storage_key"],
        )

    def _row_to_job_summary(self, row: RowMapping) -> KnowledgeJobSummary:
        return KnowledgeJobSummary(
            id=str(row["id"]),
            job_type=str(row["job_type"]),
            provider=str(row["provider"]),
            status=str(row["status"]),
            document_ids=json.loads(row["document_ids_json"]),
            progress_current=int(row["progress_current"]),
            progress_total=int(row["progress_total"]),
            error_message=row["error_message"],
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
            started_at=datetime.fromisoformat(str(row["started_at"])) if row["started_at"] else None,
            finished_at=datetime.fromisoformat(str(row["finished_at"])) if row["finished_at"] else None,
        )

    def _row_to_job_detail(self, row: RowMapping) -> KnowledgeJobDetail:
        summary = self._row_to_job_summary(row)
        result_json = row["result_json"]
        return KnowledgeJobDetail(
            **summary.model_dump(),
            result=json.loads(result_json) if result_json else None,
        )

    def _row_to_session(self, row: RowMapping) -> SessionState:
        references = [ReferenceCard(**item) for item in json.loads(row["references_json"])]
        return SessionState(
            id=str(row["id"]),
            title=str(row["title"]),
            topic_type=str(row["topic_type"]),
            slots=json.loads(row["slots_json"]),
            missing_slots=json.loads(row["missing_slots_json"]),
            risk_alerts=json.loads(row["risk_alerts_json"]),
            references=references,
            prd_markdown=str(row["prd_markdown"]),
            messages=self.list_messages(str(row["id"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
        )

    def _row_to_session_summary(self, row: RowMapping) -> SessionSummary:
        preview = str(row["last_message_preview"] or "").replace("\n", " ").strip()
        if len(preview) > 120:
            preview = f"{preview[:120]}..."
        return SessionSummary(
            id=str(row["id"]),
            title=str(row["title"]),
            topic_type=str(row["topic_type"]),
            message_count=int(row["message_count"]),
            last_message_preview=preview,
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
        )


database = Database(settings.database_url)
