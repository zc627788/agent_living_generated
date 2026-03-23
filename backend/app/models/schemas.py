"""后端 API 与服务层共享的数据模型定义。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime


class ReferenceCard(BaseModel):
    id: str
    title: str
    source: str
    source_type: str
    snippet: str
    url: str | None = None
    thumbnail_url: str | None = None
    score: float
    section_path: str
    tags: list[str] = Field(default_factory=list)


class SessionState(BaseModel):
    id: str
    title: str
    topic_type: str
    slots: dict[str, str] = Field(default_factory=dict)
    missing_slots: list[str] = Field(default_factory=list)
    risk_alerts: list[str] = Field(default_factory=list)
    prd_markdown: str = ""
    references: list[ReferenceCard] = Field(default_factory=list)
    messages: list[Message] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SessionSummary(BaseModel):
    id: str
    title: str
    topic_type: str
    message_count: int = 0
    last_message_preview: str = ""
    created_at: datetime
    updated_at: datetime


class RetrievalOptions(BaseModel):
    """检索调参模型，前端滑块和后端召回逻辑一一对应。"""
    limit: int = Field(default=4, ge=1, le=12)
    candidate_multiplier: int = Field(default=3, ge=1, le=8)
    keyword_weight: float = Field(default=0.06, ge=0.0, le=1.0)
    neighbor_hops: int = Field(default=1, ge=0, le=2)
    min_score: float = Field(default=0.15, ge=0.0, le=1.0)
    use_query_rewrite: bool = True
    document_ids: list[str] = Field(default_factory=list)


class SessionCreateRequest(BaseModel):
    initial_message: str = Field(min_length=1, max_length=4000)
    retrieval: RetrievalOptions = Field(default_factory=RetrievalOptions)


class MessageCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    retrieval: RetrievalOptions = Field(default_factory=RetrievalOptions)


class SessionReply(BaseModel):
    session: SessionState
    assistant_message: Message


class SessionTitleUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class HealthResponse(BaseModel):
    status: str
    rag_provider: str
    knowledge_documents: int
    knowledge_chunks: int
    llm_model: str
    embedding_model: str
    graphrag_available: bool = False
    graphrag_chat_model: str | None = None
    graphrag_embedding_model: str | None = None


class KnowledgeRefreshResponse(BaseModel):
    documents: int
    chunks: int
    provider: str


class KnowledgeDocumentSummary(BaseModel):
    id: str
    title: str
    source_type: str
    source: str
    url: str | None = None
    thumbnail_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    chunk_count: int
    created_at: datetime
    updated_at: datetime
    is_builtin: bool = False


class KnowledgeDocumentDetail(KnowledgeDocumentSummary):
    content: str
    origin_file_name: str | None = None
    storage_key: str | None = None


class KnowledgeDocumentVersionSummary(BaseModel):
    id: str
    document_id: str
    version_number: int
    title: str
    source_type: str
    source: str
    tags: list[str] = Field(default_factory=list)
    change_summary: str | None = None
    created_at: datetime


class KnowledgeDocumentVersionDetail(KnowledgeDocumentVersionSummary):
    url: str | None = None
    thumbnail_url: str | None = None
    content: str
    origin_file_name: str | None = None
    storage_key: str | None = None


class KnowledgeChunkPreview(BaseModel):
    id: str
    document_id: str
    title: str
    section_path: str
    content: str
    tags: list[str] = Field(default_factory=list)
    chunk_index: int


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    topic_type: str = ""
    retrieval: RetrievalOptions = Field(default_factory=RetrievalOptions)


class KnowledgeUploadPayload(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    source_type: str = Field(min_length=1, max_length=40)
    source: str = Field(min_length=1, max_length=120)
    tags: str = ""
    url: str | None = None
    thumbnail_url: str | None = None


class KnowledgeDocumentUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    source_type: str = Field(min_length=1, max_length=40)
    source: str = Field(min_length=1, max_length=120)
    tags: list[str] = Field(default_factory=list)
    url: str | None = None
    thumbnail_url: str | None = None
    content: str = Field(min_length=1)


class BatchReindexRequest(BaseModel):
    document_ids: list[str] = Field(default_factory=list)


class GraphBuildRequest(BaseModel):
    document_ids: list[str] = Field(default_factory=list)
    method: Literal["standard", "fast"] = "standard"


class KnowledgeJobSummary(BaseModel):
    id: str
    job_type: str
    provider: str
    status: Literal["pending", "running", "succeeded", "failed"]
    document_ids: list[str] = Field(default_factory=list)
    progress_current: int = 0
    progress_total: int = 0
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class KnowledgeJobDetail(KnowledgeJobSummary):
    result: dict[str, Any] | None = None


class GraphIndexSummary(BaseModel):
    job_id: str
    method: str
    created_at: datetime
    document_ids: list[str] = Field(default_factory=list)
    document_titles: list[str] = Field(default_factory=list)
    artifact_counts: dict[str, int] = Field(default_factory=dict)
    workspace_dir: str | None = None
    graphml_path: str | None = None


class GraphNode(BaseModel):
    id: str
    label: str
    kind: str
    size: float = 1.0
    score: float = 0.0
    community: str | None = None
    description: str | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    weight: float = 1.0
    label: str | None = None


class GraphCommunityReport(BaseModel):
    id: str
    title: str
    summary: str
    rank: float = 0.0


class GraphQueryRequest(BaseModel):
    job_id: str
    query: str = Field(min_length=1, max_length=1000)
    mode: Literal["local", "global"] = "local"
    entity_limit: int = Field(default=12, ge=3, le=40)
    edge_limit: int = Field(default=20, ge=0, le=80)
    community_limit: int = Field(default=3, ge=0, le=10)


class GraphQueryResponse(BaseModel):
    answer: str
    rewritten_query: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    reports: list[GraphCommunityReport] = Field(default_factory=list)
    artifacts: dict[str, int] = Field(default_factory=dict)
