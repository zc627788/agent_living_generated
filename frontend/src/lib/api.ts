// 前端 API 访问层。
// 这里统一封装普通 JSON 请求、SSE 会话流和各类后台运维接口，避免页面组件直接操作 fetch 细节。

import type {
  GraphIndexSummary,
  GraphQueryResponse,
  HealthResponse,
  KnowledgeChunkPreview,
  KnowledgeDocumentDetail,
  KnowledgeDocumentSummary,
  KnowledgeDocumentVersionSummary,
  KnowledgeJobDetail,
  KnowledgeJobSummary,
  ReferenceCard,
  RetrievalOptions,
  SessionReply,
  SessionSummary,
  SessionState,
  TraceStep,
} from "@/lib/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

export function buildDefaultRetrievalOptions(): RetrievalOptions {
  return {
    limit: 4,
    candidate_multiplier: 3,
    keyword_weight: 0.06,
    neighbor_hops: 1,
    min_score: 0.15,
    use_query_rewrite: true,
    document_ids: [],
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Request failed.");
  }

  return response.json() as Promise<T>;
}

export function fetchHealth() {
  return request<HealthResponse>("/health");
}

export function createSession(initialMessage: string, retrieval = buildDefaultRetrievalOptions()) {
  return request<SessionReply>("/sessions", {
    method: "POST",
    body: JSON.stringify({ initial_message: initialMessage, retrieval }),
  });
}

export function appendMessage(
  sessionId: string,
  content: string,
  retrieval = buildDefaultRetrievalOptions(),
) {
  return request<SessionReply>(`/sessions/${sessionId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content, retrieval }),
  });
}

type StreamHandlers = {
  onStatus?: (payload: TraceStep) => void;
  onDelta?: (content: string) => void;
  onSession?: (payload: SessionReply) => void;
};

function parseEventBlock(block: string) {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }
  return {
    event,
    data: dataLines.length ? JSON.parse(dataLines.join("\n")) : null,
  };
}

async function streamSession(
  path: string,
  body: Record<string, unknown>,
  handlers: StreamHandlers,
) {
  // SSE 协议本质是文本流，这里手工拆分 event/data 片段，确保浏览器环境下稳定可控。
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(body),
    cache: "no-store",
  });

  if (!response.ok || !response.body) {
    const message = await response.text();
    throw new Error(message || "Stream failed.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let finalReply: SessionReply | null = null;

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      if (!part.trim()) {
        continue;
      }
      const parsed = parseEventBlock(part);
      if (parsed.event === "status" && parsed.data) {
        handlers.onStatus?.(parsed.data as TraceStep);
      }
      if (parsed.event === "delta" && parsed.data) {
        handlers.onDelta?.(String((parsed.data as { content: string }).content ?? ""));
      }
      if (parsed.event === "session" && parsed.data) {
        finalReply = parsed.data as SessionReply;
        handlers.onSession?.(finalReply);
      }
      if (parsed.event === "error" && parsed.data) {
        throw new Error(String((parsed.data as { message: string }).message ?? "Stream failed."));
      }
    }

    if (done) {
      break;
    }
  }

  if (!finalReply) {
    throw new Error("Stream finished without session payload.");
  }
  return finalReply;
}

export function streamCreateSession(
  initialMessage: string,
  retrieval: RetrievalOptions,
  handlers: StreamHandlers,
) {
  return streamSession("/sessions/stream", { initial_message: initialMessage, retrieval }, handlers);
}

export function streamAppendMessage(
  sessionId: string,
  content: string,
  retrieval: RetrievalOptions,
  handlers: StreamHandlers,
) {
  return streamSession(`/sessions/${sessionId}/messages/stream`, { content, retrieval }, handlers);
}

export function fetchSession(sessionId: string) {
  return request<SessionState>(`/sessions/${sessionId}`);
}

export function listSessions(limit = 50) {
  return request<SessionSummary[]>(`/sessions?limit=${limit}`);
}

export function renameSession(sessionId: string, title: string) {
  return request<SessionState>(`/sessions/${sessionId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

export function deleteSession(sessionId: string) {
  return request<{ status: string; session_id: string }>(`/sessions/${sessionId}`, {
    method: "DELETE",
  });
}

export function listKnowledgeDocuments() {
  return request<KnowledgeDocumentSummary[]>("/knowledge/documents");
}

export function fetchKnowledgeDocument(documentId: string) {
  return request<KnowledgeDocumentDetail>(`/knowledge/documents/${documentId}`);
}

export function listKnowledgeDocumentVersions(documentId: string) {
  return request<KnowledgeDocumentVersionSummary[]>(`/knowledge/documents/${documentId}/versions`);
}

export function restoreKnowledgeDocumentVersion(documentId: string, versionId: string) {
  return request<KnowledgeDocumentDetail>(
    `/knowledge/documents/${documentId}/versions/${versionId}/restore`,
    {
      method: "POST",
    },
  );
}

export function listKnowledgeChunks(documentId?: string) {
  const query = documentId ? `?document_id=${encodeURIComponent(documentId)}` : "";
  return request<KnowledgeChunkPreview[]>(`/knowledge/chunks${query}`);
}

export function refreshKnowledge() {
  return request<{ documents: number; chunks: number; provider: string }>("/knowledge/refresh", {
    method: "POST",
  });
}

export function searchKnowledge(
  query: string,
  topicType = "",
  retrieval = buildDefaultRetrievalOptions(),
) {
  return request<ReferenceCard[]>("/knowledge/search-test", {
    method: "POST",
    body: JSON.stringify({ query, topic_type: topicType, retrieval }),
  });
}

export async function uploadKnowledge(formData: FormData) {
  const response = await fetch(`${API_BASE_URL}/knowledge/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Upload failed.");
  }

  return response.json() as Promise<KnowledgeDocumentDetail>;
}

export function updateKnowledgeDocument(
  documentId: string,
  payload: {
    title: string;
    source_type: string;
    source: string;
    tags: string[];
    url?: string | null;
    thumbnail_url?: string | null;
    content: string;
  },
) {
  return request<KnowledgeDocumentDetail>(`/knowledge/documents/${documentId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function deleteKnowledgeDocument(documentId: string) {
  return request<{ documents: number; chunks: number }>(`/knowledge/documents/${documentId}`, {
    method: "DELETE",
  });
}

export function reindexKnowledgeDocument(documentId: string) {
  return request<{ documents: number; chunks: number; provider: string }>(
    `/knowledge/documents/${documentId}/reindex`,
    {
      method: "POST",
    },
  );
}

export function listKnowledgeJobs(limit = 20) {
  return request<KnowledgeJobSummary[]>(`/knowledge/jobs?limit=${limit}`);
}

export function fetchKnowledgeJob(jobId: string) {
  return request<KnowledgeJobDetail>(`/knowledge/jobs/${jobId}`);
}

export function createBatchReindexJob(documentIds: string[]) {
  return request<KnowledgeJobDetail>("/knowledge/jobs/reindex", {
    method: "POST",
    body: JSON.stringify({ document_ids: documentIds }),
  });
}

export function createGraphRagJob(documentIds: string[], method: "standard" | "fast" = "standard") {
  return request<KnowledgeJobDetail>("/knowledge/jobs/graphrag", {
    method: "POST",
    body: JSON.stringify({ document_ids: documentIds, method }),
  });
}

export function listGraphIndexes(limit = 10) {
  return request<GraphIndexSummary[]>(`/knowledge/graph/indexes?limit=${limit}`);
}

export function queryGraph(payload: {
  job_id: string;
  query: string;
  mode: "local" | "global";
  entity_limit: number;
  edge_limit: number;
  community_limit: number;
}) {
  return request<GraphQueryResponse>("/knowledge/graph/query", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function exportSessionDocx(sessionId: string, fileName: string) {
  // 导出由后端生成完整 docx，前端只负责触发下载，不参与文档拼装。
  const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/export/docx`, {
    method: "GET",
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Export failed.");
  }
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName.endsWith(".docx") ? fileName : `${fileName}.docx`;
  anchor.click();
  window.URL.revokeObjectURL(url);
}
