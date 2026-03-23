// 前端共享类型定义。
// 所有页面和 API 层都依赖这里的结构，保证字段名称与后端 Pydantic 模型保持一致。

export type Role = "user" | "assistant" | "system";

export interface Message {
  id: string;
  role: Role;
  content: string;
  created_at: string;
}

export interface TracePayload {
  latest_message?: string;
  history_count?: number;
  current_topic_type?: string | null;
  topic_type?: string;
  topic_reason?: string;
  title?: string;
  query?: string;
  rewritten_query?: string;
  missing_slots?: string[];
  risk_alerts?: string[];
  need_follow_up?: boolean;
  references?: Array<{
    title: string;
    source: string;
    score: number;
    section_path: string;
  }>;
  slots?: Record<string, string>;
  review_issues?: string[];
  prd_preview?: string;
  assistant_mode?: string;
  retrieval?: {
    limit: number;
    candidate_multiplier: number;
    keyword_weight: number;
    neighbor_hops: number;
    min_score: number;
    use_query_rewrite: boolean;
    document_ids: string[];
  };
}

export interface TraceStep {
  trace_id: string;
  node: string;
  message: string;
  detail?: string;
  phase: "started" | "completed" | "failed";
  status: "running" | "succeeded" | "failed";
  created_at: string;
  started_at?: string;
  finished_at?: string;
  input?: TracePayload;
  output?: TracePayload;
  error?: string;
}

export interface ReferenceCard {
  id: string;
  title: string;
  source: string;
  source_type: string;
  snippet: string;
  url?: string | null;
  thumbnail_url?: string | null;
  score: number;
  section_path: string;
  tags: string[];
}

export interface SessionState {
  id: string;
  title: string;
  topic_type: string;
  slots: Record<string, string>;
  missing_slots: string[];
  risk_alerts: string[];
  prd_markdown: string;
  references: ReferenceCard[];
  messages: Message[];
  created_at: string;
  updated_at: string;
}

export interface SessionSummary {
  id: string;
  title: string;
  topic_type: string;
  message_count: number;
  last_message_preview: string;
  created_at: string;
  updated_at: string;
}

export interface RetrievalOptions {
  limit: number;
  candidate_multiplier: number;
  keyword_weight: number;
  neighbor_hops: number;
  min_score: number;
  use_query_rewrite: boolean;
  document_ids: string[];
}

export interface SessionReply {
  session: SessionState;
  assistant_message: Message;
}

export interface HealthResponse {
  status: string;
  rag_provider: string;
  knowledge_documents: number;
  knowledge_chunks: number;
  llm_model: string;
  embedding_model: string;
  graphrag_available: boolean;
  graphrag_chat_model?: string | null;
  graphrag_embedding_model?: string | null;
}

export interface KnowledgeDocumentSummary {
  id: string;
  title: string;
  source_type: string;
  source: string;
  url?: string | null;
  thumbnail_url?: string | null;
  tags: string[];
  chunk_count: number;
  created_at: string;
  updated_at: string;
  is_builtin: boolean;
}

export interface KnowledgeDocumentDetail extends KnowledgeDocumentSummary {
  content: string;
  origin_file_name?: string | null;
  storage_key?: string | null;
}

export interface KnowledgeChunkPreview {
  id: string;
  document_id: string;
  title: string;
  section_path: string;
  content: string;
  tags: string[];
  chunk_index: number;
}

export interface KnowledgeDocumentVersionSummary {
  id: string;
  document_id: string;
  version_number: number;
  title: string;
  source_type: string;
  source: string;
  tags: string[];
  change_summary?: string | null;
  created_at: string;
}

export interface KnowledgeJobSummary {
  id: string;
  job_type: string;
  provider: string;
  status: "pending" | "running" | "succeeded" | "failed";
  document_ids: string[];
  progress_current: number;
  progress_total: number;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface KnowledgeJobDetail extends KnowledgeJobSummary {
  result?: Record<string, unknown> | null;
}

export interface GraphIndexSummary {
  job_id: string;
  method: string;
  created_at: string;
  document_ids: string[];
  document_titles: string[];
  artifact_counts: Record<string, number>;
  workspace_dir?: string | null;
  graphml_path?: string | null;
}

export interface GraphNode {
  id: string;
  label: string;
  kind: string;
  size: number;
  score: number;
  community?: string | null;
  description?: string | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  weight: number;
  label?: string | null;
}

export interface GraphCommunityReport {
  id: string;
  title: string;
  summary: string;
  rank: number;
}

export interface GraphQueryResponse {
  answer: string;
  rewritten_query: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  reports: GraphCommunityReport[];
  artifacts: Record<string, number>;
}
