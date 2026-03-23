"""HTTP 路由层。

负责把前端请求转成服务调用，并统一处理会话持久化、SSE 输出和知识库运维接口。
"""

from __future__ import annotations

import json
import uuid
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse

from app.core.config import settings
from app.db.database import database
from app.models.schemas import (
    BatchReindexRequest,
    GraphBuildRequest,
    GraphIndexSummary,
    GraphQueryRequest,
    GraphQueryResponse,
    HealthResponse,
    KnowledgeChunkPreview,
    KnowledgeDocumentDetail,
    KnowledgeDocumentSummary,
    KnowledgeDocumentUpdateRequest,
    KnowledgeDocumentVersionSummary,
    KnowledgeJobDetail,
    KnowledgeJobSummary,
    KnowledgeRefreshResponse,
    KnowledgeSearchRequest,
    MessageCreateRequest,
    SessionCreateRequest,
    SessionReply,
    SessionSummary,
    SessionState,
    SessionTitleUpdateRequest,
)
from app.services.docx_export import markdown_to_docx_bytes
from app.services.graphrag_query import graphrag_query_service
from app.services.graphrag_service import graphrag_service
from app.services.interview import InterviewResult, interview_service
from app.services.knowledge_base import knowledge_base_service
from app.services.knowledge_jobs import knowledge_job_service
from app.services.object_storage import object_storage_service
from app.services.retriever import retriever

router = APIRouter()


def ensure_runtime_ready() -> tuple[int, int]:
    """确保数据库与内置知识库都已可用。"""
    database.initialize()
    return knowledge_base_service.ensure_seeded()


def raise_service_error(error: ValueError) -> None:
    detail = str(error)
    status_code = 404 if "不存在" in detail else 400
    raise HTTPException(status_code=status_code, detail=detail)


def as_sse(event: str, data: dict) -> str:
    """把事件包装成标准 SSE 文本块。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def persist_new_session(initial_message: str, result: InterviewResult) -> SessionReply:
    """首次对话完成后，把会话主记录与首轮消息一并落库。"""
    session_id = database.create_session(
        title=result.title,
        topic_type=result.topic_type,
        slots=result.slots,
        missing_slots=result.missing_slots,
        risk_alerts=result.risk_alerts,
        references=result.references,
        prd_markdown=result.prd_markdown,
    )
    database.create_message(session_id, "user", initial_message)
    assistant_message = database.create_message(session_id, "assistant", result.assistant_message)
    session = database.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=500, detail="Session creation failed.")
    return SessionReply(session=session, assistant_message=assistant_message)


def persist_session_message(session_id: str, content: str, result: InterviewResult) -> SessionReply:
    """多轮追问时更新会话快照，并补写本轮消息。"""
    database.create_message(session_id, "user", content)
    database.update_session(
        session_id=session_id,
        title=result.title,
        topic_type=result.topic_type,
        slots=result.slots,
        missing_slots=result.missing_slots,
        risk_alerts=result.risk_alerts,
        references=result.references,
        prd_markdown=result.prd_markdown,
    )
    assistant_message = database.create_message(session_id, "assistant", result.assistant_message)
    session = database.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=500, detail="Session update failed.")
    return SessionReply(session=session, assistant_message=assistant_message)


@router.get("/health", response_model=HealthResponse)
def healthcheck() -> HealthResponse:
    documents, chunks = ensure_runtime_ready()
    return HealthResponse(
        status="ok",
        rag_provider=settings.rag_provider,
        knowledge_documents=documents,
        knowledge_chunks=chunks,
        llm_model=settings.qwen_chat_model,
        embedding_model=settings.qwen_embedding_model,
        graphrag_available=graphrag_service.is_available(),
        graphrag_chat_model=settings.graphrag_chat_model,
        graphrag_embedding_model=settings.graphrag_embedding_model,
    )


@router.post("/knowledge/refresh", response_model=KnowledgeRefreshResponse)
def refresh_knowledge() -> KnowledgeRefreshResponse:
    ensure_runtime_ready()
    documents, chunks = knowledge_base_service.refresh()
    return KnowledgeRefreshResponse(documents=documents, chunks=chunks, provider=settings.rag_provider)


@router.get("/knowledge/documents", response_model=list[KnowledgeDocumentSummary])
def list_documents() -> list[KnowledgeDocumentSummary]:
    ensure_runtime_ready()
    return knowledge_base_service.list_documents()


@router.get("/knowledge/documents/{document_id}", response_model=KnowledgeDocumentDetail)
def get_document(document_id: str) -> KnowledgeDocumentDetail:
    ensure_runtime_ready()
    document = knowledge_base_service.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在。")
    return document


@router.get("/knowledge/documents/{document_id}/versions", response_model=list[KnowledgeDocumentVersionSummary])
def list_document_versions(document_id: str) -> list[KnowledgeDocumentVersionSummary]:
    ensure_runtime_ready()
    try:
        return knowledge_base_service.list_document_versions(document_id)
    except ValueError as error:
        raise_service_error(error)


@router.post("/knowledge/documents/{document_id}/versions/{version_id}/restore", response_model=KnowledgeDocumentDetail)
def restore_document_version(document_id: str, version_id: str) -> KnowledgeDocumentDetail:
    ensure_runtime_ready()
    try:
        return knowledge_base_service.restore_document_version(document_id, version_id)
    except ValueError as error:
        raise_service_error(error)


@router.put("/knowledge/documents/{document_id}", response_model=KnowledgeDocumentDetail)
def update_document(document_id: str, payload: KnowledgeDocumentUpdateRequest) -> KnowledgeDocumentDetail:
    ensure_runtime_ready()
    try:
        return knowledge_base_service.update_document(document_id, payload)
    except ValueError as error:
        raise_service_error(error)


@router.delete("/knowledge/documents/{document_id}")
def delete_document(document_id: str) -> dict[str, int]:
    ensure_runtime_ready()
    try:
        documents, chunks = knowledge_base_service.delete_document(document_id)
    except ValueError as error:
        raise_service_error(error)
    return {"documents": documents, "chunks": chunks}


@router.post("/knowledge/documents/{document_id}/reindex")
def reindex_document(document_id: str) -> dict[str, int | str]:
    ensure_runtime_ready()
    try:
        documents, chunks = knowledge_base_service.reindex_documents([document_id])
    except ValueError as error:
        raise_service_error(error)
    return {"documents": documents, "chunks": chunks, "provider": settings.rag_provider}


@router.get("/knowledge/chunks", response_model=list[KnowledgeChunkPreview])
def list_chunks(document_id: str | None = None) -> list[KnowledgeChunkPreview]:
    ensure_runtime_ready()
    return knowledge_base_service.list_chunks(document_id=document_id)


@router.get("/knowledge/jobs", response_model=list[KnowledgeJobSummary])
def list_jobs(limit: int = 20) -> list[KnowledgeJobSummary]:
    database.initialize()
    return knowledge_job_service.list_jobs(limit=limit)


@router.get("/knowledge/jobs/{job_id}", response_model=KnowledgeJobDetail)
def get_job(job_id: str) -> KnowledgeJobDetail:
    database.initialize()
    job = knowledge_job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在。")
    return job


@router.post("/knowledge/jobs/reindex", response_model=KnowledgeJobDetail)
def create_reindex_job(payload: BatchReindexRequest) -> KnowledgeJobDetail:
    ensure_runtime_ready()
    return knowledge_job_service.submit_reindex_job(payload.document_ids)


@router.post("/knowledge/jobs/graphrag", response_model=KnowledgeJobDetail)
def create_graphrag_job(payload: GraphBuildRequest) -> KnowledgeJobDetail:
    ensure_runtime_ready()
    return knowledge_job_service.submit_graphrag_job(payload.document_ids, payload.method)


@router.get("/knowledge/graph/indexes", response_model=list[GraphIndexSummary])
def list_graph_indexes(limit: int = 10) -> list[GraphIndexSummary]:
    database.initialize()
    return graphrag_query_service.list_indexes(limit=limit)


@router.post("/knowledge/graph/query", response_model=GraphQueryResponse)
def query_graph(payload: GraphQueryRequest) -> GraphQueryResponse:
    database.initialize()
    try:
        return graphrag_query_service.query(
            job_id=payload.job_id,
            query=payload.query,
            mode=payload.mode,
            entity_limit=payload.entity_limit,
            edge_limit=payload.edge_limit,
            community_limit=payload.community_limit,
        )
    except ValueError as error:
        raise_service_error(error)


@router.post("/knowledge/search-test")
def search_knowledge(payload: KnowledgeSearchRequest):
    ensure_runtime_ready()
    return retriever.search(payload.query, payload.topic_type, payload.retrieval)


@router.post("/knowledge/upload", response_model=KnowledgeDocumentDetail)
async def upload_knowledge(
    title: str = Form(...),
    source_type: str = Form(...),
    source: str = Form(...),
    tags: str = Form(""),
    url: str | None = Form(None),
    thumbnail_url: str | None = Form(None),
    file: UploadFile = File(...),
) -> KnowledgeDocumentDetail:
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空。")

    suffix = f".{file.filename.lower().rsplit('.', 1)[-1]}" if "." in file.filename else ""
    if suffix not in {".md", ".txt", ".docx"}:
        raise HTTPException(status_code=400, detail="仅支持 .md / .txt / .docx 文件。")

    content = await file.read()
    try:
        return knowledge_base_service.save_upload(
            file_name=file.filename,
            content=content,
            title=title,
            source_type=source_type,
            source=source,
            tags=[item.strip() for item in tags.split(",") if item.strip()],
            url=url,
            thumbnail_url=thumbnail_url,
        )
    except ValueError as error:
        raise_service_error(error)


@router.post("/sessions", response_model=SessionReply)
def create_session(payload: SessionCreateRequest) -> SessionReply:
    ensure_runtime_ready()
    result = interview_service.run(
        latest_message=payload.initial_message,
        history=[],
        current_slots={},
        current_topic_type=None,
        retrieval=payload.retrieval,
    )
    return persist_new_session(payload.initial_message, result)


@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions(limit: int = 50) -> list[SessionSummary]:
    database.initialize()
    return database.list_sessions(limit=limit)


@router.post("/sessions/stream")
def create_session_stream(payload: SessionCreateRequest) -> StreamingResponse:
    ensure_runtime_ready()

    def event_stream():
        try:
            for event in interview_service.stream(
                latest_message=payload.initial_message,
                history=[],
                current_slots={},
                current_topic_type=None,
                retrieval=payload.retrieval,
            ):
                if event["event"] == "result":
                    result: InterviewResult = event["data"]
                    response = persist_new_session(payload.initial_message, result)
                    yield as_sse("session", response.model_dump(mode="json"))
                else:
                    yield as_sse(event["event"], event["data"])
            yield as_sse("done", {"ok": True})
        except Exception as error:
            yield as_sse("error", {"message": str(error)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions/{session_id}", response_model=SessionState)
def get_session(session_id: str) -> SessionState:
    database.initialize()
    session = database.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


@router.patch("/sessions/{session_id}", response_model=SessionState)
def rename_session(session_id: str, payload: SessionTitleUpdateRequest) -> SessionState:
    database.initialize()
    session = database.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    database.update_session_title(session_id, payload.title)
    updated = database.get_session(session_id)
    if updated is None:
        raise HTTPException(status_code=500, detail="Session update failed.")
    return updated


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str) -> dict[str, str]:
    database.initialize()
    session = database.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    database.delete_session(session_id)
    return {"status": "ok", "session_id": session_id}


@router.post("/sessions/{session_id}/messages", response_model=SessionReply)
def append_message(session_id: str, payload: MessageCreateRequest) -> SessionReply:
    ensure_runtime_ready()
    session = database.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    result = interview_service.run(
        latest_message=payload.content,
        history=[message.content for message in session.messages],
        current_slots=session.slots,
        current_topic_type=session.topic_type,
        retrieval=payload.retrieval,
    )
    return persist_session_message(session_id, payload.content, result)


@router.post("/sessions/{session_id}/messages/stream")
def append_message_stream(session_id: str, payload: MessageCreateRequest) -> StreamingResponse:
    ensure_runtime_ready()
    session = database.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    def event_stream():
        try:
            for event in interview_service.stream(
                latest_message=payload.content,
                history=[message.content for message in session.messages],
                current_slots=session.slots,
                current_topic_type=session.topic_type,
                retrieval=payload.retrieval,
            ):
                if event["event"] == "result":
                    result: InterviewResult = event["data"]
                    response = persist_session_message(session_id, payload.content, result)
                    yield as_sse("session", response.model_dump(mode="json"))
                else:
                    yield as_sse(event["event"], event["data"])
            yield as_sse("done", {"ok": True})
        except Exception as error:
            yield as_sse("error", {"message": str(error)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions/{session_id}/export/docx")
def export_session_docx(session_id: str) -> Response:
    database.initialize()
    session = database.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    content = markdown_to_docx_bytes(session.title, session.prd_markdown)
    object_key = f"exports/{session_id}/{uuid.uuid4().hex}.docx"
    object_storage_service.upload_bytes(
        object_key,
        content,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    file_name = quote(f"{session.title}.docx")
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{file_name}",
        "X-Storage-Key": object_key,
    }
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )
