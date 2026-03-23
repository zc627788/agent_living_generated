"use client";

import { startTransition, useEffect, useState } from "react";

import { MoreOutlined } from "@ant-design/icons";
import {
  Badge,
  Button,
  Card,
  Descriptions,
  Dropdown,
  Drawer,
  Empty,
  Input,
  Modal,
  Progress,
  Select,
  Slider,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Timeline,
  Typography,
  message,
} from "antd";
import { useMount, useRequest } from "ahooks";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { InlineNotice } from "@/components/inline-notice";
import { ThumbnailPreview } from "@/components/thumbnail-preview";
import {
  buildDefaultRetrievalOptions,
  exportSessionDocx,
  deleteSession,
  fetchSession,
  fetchHealth,
  listKnowledgeDocuments,
  listSessions,
  renameSession,
  streamAppendMessage,
  streamCreateSession,
} from "@/lib/api";
import type {
  KnowledgeDocumentSummary,
  Message,
  ReferenceCard,
  RetrievalOptions,
  SessionSummary,
  SessionState,
  TracePayload,
  TraceStep,
} from "@/lib/types";

const QUICK_PROMPTS = [
  "我要做一个春节抽奖活动专题页，重点突出奖品、参与门槛和活动时间。",
  "准备上线一个新版本专题页，核心卖点和视觉氛围。",
  "我们要做春招招聘页，面向前端和设计岗位，希望页面更年轻。",
] as const;

function formatDateTime(value?: string | null) {
  return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "-";
}

function getRoleLabel(role: Message["role"]) {
  if (role === "user") return "需求方";
  if (role === "assistant") return "Agent";
  return "流程事件";
}

function mergeMessages(
  session: SessionState | null,
  pendingUserMessage: string,
  pendingAssistantMessage: string,
  activityLog: TraceStep[],
) {
  const items: Message[] = [...(session?.messages ?? [])];

  if (pendingUserMessage) {
    items.push({
      id: "pending-user",
      role: "user",
      content: pendingUserMessage,
      created_at: new Date().toISOString(),
    });
  }

  activityLog.forEach((item) => {
    items.push({
      id: `status-${item.created_at}-${item.trace_id}`,
      role: "system",
      content: `${item.message}\n${item.detail ?? ""}`.trim(),
      created_at: item.created_at,
    });
  });

  if (pendingAssistantMessage) {
    items.push({
      id: "pending-assistant",
      role: "assistant",
      content: pendingAssistantMessage,
      created_at: new Date().toISOString(),
    });
  }

  return items;
}

function upsertTraceStep(current: TraceStep[], incoming: TraceStep) {
  const existingIndex = current.findIndex((item) => item.trace_id === incoming.trace_id);
  if (existingIndex < 0) {
    return [...current, incoming];
  }
  const next = [...current];
  next[existingIndex] = {
    ...next[existingIndex],
    ...incoming,
  };
  return next;
}

function countTraceByStatus(steps: TraceStep[], status: TraceStep["status"]) {
  return steps.filter((item) => item.status === status).length;
}

function prettyTracePayload(payload?: TracePayload) {
  if (!payload) {
    return "暂无数据";
  }
  return JSON.stringify(payload, null, 2);
}

export function Workbench() {
  const [input, setInput] = useState<string>(QUICK_PROMPTS[0]);
  const [retrieval, setRetrieval] = useState<RetrievalOptions>(buildDefaultRetrievalOptions());
  const [storageReady, setStorageReady] = useState(false);
  const [sessionList, setSessionList] = useState<SessionSummary[]>([]);
  const [session, setSession] = useState<SessionState | null>(null);
  const [knowledgeDocuments, setKnowledgeDocuments] = useState<KnowledgeDocumentSummary[]>([]);
  const [backendError, setBackendError] = useState("");
  const [pendingUserMessage, setPendingUserMessage] = useState("");
  const [pendingAssistantMessage, setPendingAssistantMessage] = useState("");
  const [activityLog, setActivityLog] = useState<TraceStep[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [activeReference, setActiveReference] = useState<ReferenceCard | null>(null);
  const [traceModalOpen, setTraceModalOpen] = useState(false);
  const [activeTraceId, setActiveTraceId] = useState("");
  const [renameModalOpen, setRenameModalOpen] = useState(false);
  const [renameSessionId, setRenameSessionId] = useState("");
  const [renameValue, setRenameValue] = useState("");
  const [apiMessage, contextHolder] = message.useMessage();

  const bootstrapRequest = useRequest(
    async () => {
      const [healthResult, documentList, sessionSummaries] = await Promise.all([
        fetchHealth(),
        listKnowledgeDocuments(),
        listSessions(),
      ]);
      return { healthResult, documentList, sessionSummaries };
    },
    {
      manual: true,
      onSuccess(result) {
        setKnowledgeDocuments(result.documentList);
        setSessionList(result.sessionSummaries);
        setBackendError("");
      },
      onError(error) {
        setBackendError(error.message);
      },
    },
  );

  useMount(() => {
    bootstrapRequest.run();
  });

  useEffect(() => {
    try {
      const savedInput = window.localStorage.getItem("topic-agent-input");
      const savedRetrieval = window.localStorage.getItem("topic-agent-retrieval");
      const savedSessionId = window.localStorage.getItem("topic-agent-session-id");
      if (savedInput) {
        setInput(savedInput);
      }
      if (savedRetrieval) {
        const parsed = JSON.parse(savedRetrieval) as Partial<RetrievalOptions>;
        setRetrieval({
          ...buildDefaultRetrievalOptions(),
          ...parsed,
          document_ids: Array.isArray(parsed.document_ids) ? parsed.document_ids : [],
        });
      }
      if (savedSessionId) {
        void fetchSession(savedSessionId)
          .then((result) => {
            setSession(result);
          })
          .catch(() => {
            window.localStorage.removeItem("topic-agent-session-id");
          });
      }
    } catch {
      // 本地缓存损坏时回退到默认值即可，不影响页面可用性。
    } finally {
      setStorageReady(true);
    }
  }, []);

  useEffect(() => {
    if (!storageReady) {
      return;
    }
    window.localStorage.setItem("topic-agent-input", input);
  }, [input, storageReady]);

  useEffect(() => {
    if (!storageReady) {
      return;
    }
    window.localStorage.setItem("topic-agent-retrieval", JSON.stringify(retrieval));
  }, [retrieval, storageReady]);

  useEffect(() => {
    if (!storageReady) {
      return;
    }
    if (session?.id) {
      window.localStorage.setItem("topic-agent-session-id", session.id);
      return;
    }
    window.localStorage.removeItem("topic-agent-session-id");
  }, [session?.id, storageReady]);

  useEffect(() => {
    const listener = () => {
      void bootstrapRequest.runAsync().then(() => {
        apiMessage.success("系统状态已刷新。");
      });
    };
    window.addEventListener("ops:refresh:workbench", listener);
    return () => {
      window.removeEventListener("ops:refresh:workbench", listener);
    };
  }, [apiMessage, bootstrapRequest]);

  function updateRetrieval<K extends keyof RetrievalOptions>(
    key: K,
    value: RetrievalOptions[K],
  ) {
    setRetrieval((current) => ({
      ...(current ?? buildDefaultRetrievalOptions()),
      [key]: value,
    }));
  }

  async function refreshSessionList() {
    const sessions = await listSessions();
    setSessionList(sessions);
    return sessions;
  }

  async function handleSelectSession(sessionId: string) {
    if (streaming) {
      return;
    }
    try {
      const nextSession = await fetchSession(sessionId);
      setSession(nextSession);
      setActivityLog([]);
      setPendingUserMessage("");
      setPendingAssistantMessage("");
      setActiveTraceId("");
    } catch (error) {
      apiMessage.error(error instanceof Error ? error.message : "切换对话失败。");
    }
  }

  function handleCreateConversation() {
    if (streaming) {
      return;
    }
    setSession(null);
    setActivityLog([]);
    setPendingUserMessage("");
    setPendingAssistantMessage("");
    setActiveTraceId("");
    setInput("");
  }

  function handleOpenRename(sessionItem: SessionSummary) {
    setRenameSessionId(sessionItem.id);
    setRenameValue(sessionItem.title);
    setRenameModalOpen(true);
  }

  async function handleConfirmRename() {
    if (!renameSessionId || !renameValue.trim()) {
      return;
    }
    try {
      const updated = await renameSession(renameSessionId, renameValue.trim());
      if (session?.id === renameSessionId) {
        setSession(updated);
      }
      await refreshSessionList();
      setRenameModalOpen(false);
      setRenameSessionId("");
      apiMessage.success("对话标题已更新。");
    } catch (error) {
      apiMessage.error(error instanceof Error ? error.message : "修改标题失败。");
    }
  }

  async function handleDeleteSession(sessionItem: SessionSummary) {
    if (streaming) {
      return;
    }
    try {
      await deleteSession(sessionItem.id);
      if (session?.id === sessionItem.id) {
        setSession(null);
        setActivityLog([]);
        setPendingUserMessage("");
        setPendingAssistantMessage("");
        setActiveTraceId("");
      }
      await refreshSessionList();
      apiMessage.success("对话已删除。");
    } catch (error) {
      apiMessage.error(error instanceof Error ? error.message : "删除对话失败。");
    }
  }

  async function handleSubmit(rawContent: string) {
    const content = rawContent.trim();
    if (!content || streaming) {
      return;
    }

    const currentRetrieval = retrieval;
    setStreaming(true);
    setPendingUserMessage(content);
    setPendingAssistantMessage("");
    setActivityLog([]);
    setActiveTraceId("");
    setInput("");

    try {
      const handlers = {
        onStatus(payload: TraceStep) {
          setActivityLog((current) => upsertTraceStep(current, payload));
          setActiveTraceId(payload.trace_id);
        },
        onDelta(contentChunk: string) {
          setPendingAssistantMessage((current) => current + contentChunk);
        },
        onSession(payload: { session: SessionState }) {
          startTransition(() => {
            setSession(payload.session);
          });
          setPendingUserMessage("");
          setPendingAssistantMessage("");
        },
      };

      const reply = session
        ? await streamAppendMessage(session.id, content, currentRetrieval, handlers)
        : await streamCreateSession(content, currentRetrieval, handlers);

      startTransition(() => {
        setSession(reply.session);
      });
      await refreshSessionList();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "请求失败，请稍后重试。";
      apiMessage.error(errorMessage);
      setInput(content);
    } finally {
      setStreaming(false);
      setPendingUserMessage("");
      setPendingAssistantMessage("");
    }
  }

  const currentRetrieval = retrieval;
  const messages = mergeMessages(
    session,
    pendingUserMessage,
    pendingAssistantMessage,
    activityLog,
  );
  const slotRows = Object.entries(session?.slots ?? {}).map(([field, value]) => ({
    key: field,
    field,
    value,
    status: session?.missing_slots.includes(field) ? "待补全" : "已确认",
  }));
  const completionRatio = session
    ? Math.round(
        ((Object.keys(session.slots).length - session.missing_slots.length) /
          Math.max(Object.keys(session.slots).length, 1)) *
          100,
      )
    : 0;
  const activeTraceStep =
    activityLog.find((item) => item.trace_id === activeTraceId) ??
    activityLog[activityLog.length - 1] ??
    null;
  const runningTraceCount = countTraceByStatus(activityLog, "running");
  const failedTraceCount = countTraceByStatus(activityLog, "failed");
  const completedTraceCount = countTraceByStatus(activityLog, "succeeded");

  return (
    <div className="page-stack console-page">
      {contextHolder}

      {backendError ? (
        <InlineNotice title="后端连接异常" description={backendError} tone="error" />
      ) : null}


      <div className="feature-grid">
        <div className="feature-card">
          <strong>会话采集</strong>
          <span>你只管描述需求，系统会自动判断接下来该追问、该检索还是该出稿。</span>
        </div>
        <div className="feature-card">
          <strong>结构化结果</strong>
          <span>这是一层中间态，把模糊对话转成字段，方便产品、运营、设计共同校对。</span>
        </div>
        <div className="feature-card">
          <strong>参考资料</strong>
          <span>所有命中都来自当前知识库原文切片，本轮对话不会自动写回知识库。</span>
        </div>
      </div>

      <Tabs
        className="admin-tabs admin-tabs-fill"
        items={[
          {
            key: "conversation",
            label: "会话采集",
            children: (
              <div className="workspace-grid workbench-grid">
                <Card className="panel-card panel-fill" variant="outlined">
                  <div className="chat-shell">
                    <aside className="conversation-sidebar">
                      <div className="section-header conversation-sidebar-header">
                        <div>
                          <Typography.Title level={4} className="section-title">
                            对话列表
                          </Typography.Title>
                        </div>
                        <Button size="small" onClick={handleCreateConversation}>
                          新建对话
                        </Button>
                      </div>

                      <div className="conversation-list">
                        {sessionList.length ? (
                          sessionList.map((item) => (
                            <div
                              key={item.id}
                              className={`conversation-card ${item.id === session?.id ? "is-active" : ""}`}
                              onClick={() => void handleSelectSession(item.id)}
                              style={{ marginTop: "1px" }}
                              role="button"
                              tabIndex={0}
                              onKeyDown={(event) => {
                                if (event.key === "Enter" || event.key === " ") {
                                  event.preventDefault();
                                  void handleSelectSession(item.id);
                                }
                              }}
                            >
                              <div className="conversation-card-head">
                                <Typography.Text strong ellipsis>
                                  {item.title}
                                </Typography.Text>
                                <Dropdown
                                  trigger={["click"]}
                                  menu={{
                                    items: [
                                      { key: "rename", label: "Rename" },
                                      { key: "delete", label: "Delete", danger: true },
                                    ],
                                    onClick: ({ key, domEvent }) => {
                                      domEvent.stopPropagation();
                                      if (key === "rename") {
                                        handleOpenRename(item);
                                      }
                                      if (key === "delete") {
                                        void handleDeleteSession(item);
                                      }
                                    },
                                  }}
                                >
                                  <Button
                                    type="text"
                                    size="small"
                                    className="conversation-menu-trigger"
                                    icon={<MoreOutlined />}
                                    onClick={(event) => event.stopPropagation()}
                                  />
                                </Dropdown>
                              </div>

                              <div className="conversation-card-meta">
                                <Tag color={item.id === session?.id ? "processing" : "default"}>
                                  {item.topic_type || "unknown"}
                                </Tag>
                                <span>{item.message_count} 条消息</span>
                              </div>

                              <Typography.Paragraph
                                className="helper-copy conversation-card-preview"
                                ellipsis={{ rows: 2, tooltip: item.last_message_preview || "暂无消息" }}
                              >
                                {item.last_message_preview || "暂无消息"}
                              </Typography.Paragraph>

                              <Typography.Text type="secondary" className="conversation-card-time">
                                {formatDateTime(item.updated_at)}
                              </Typography.Text>
                            </div>
                          ))
                        ) : (
                          <Empty
                            image={Empty.PRESENTED_IMAGE_SIMPLE}
                            description="还没有历史对话。"
                          />
                        )}
                      </div>
                    </aside>

                    <div className="chat-panel-stack">
                    <div className="section-header">
                      <div>
                        <Typography.Title level={4} className="section-title">
                          对话窗口
                        </Typography.Title>
                      </div>
                      <Badge
                        status={streaming ? "processing" : "success"}
                        text={streaming ? "处理中" : "等待输入"}
                      />
                    </div>

                    <div className="prompt-chip-wrap">
                      {QUICK_PROMPTS.map((prompt) => (
                        <Button key={prompt} onClick={() => setInput(prompt)}>
                          {prompt}
                        </Button>
                      ))}
                    </div>

                    <div className="chat-log">
                      {messages.length ? (
                        messages.map((item) => (
                          <div
                            key={item.id}
                            className={`chat-row ${item.role === "user" ? "is-user" : "is-agent"} ${
                              item.role === "system" ? "is-system" : ""
                            }`}
                          >
                            <div className="chat-bubble">
                              <div className="chat-meta">
                                <span>{getRoleLabel(item.role)}</span>
                                <span>{formatDateTime(item.created_at)}</span>
                              </div>
                              <div>{item.content}</div>
                            </div>
                          </div>
                        ))
                      ) : (
                        <Empty
                          image={Empty.PRESENTED_IMAGE_SIMPLE}
                          description="输入一句专题需求后，这里会展示用户消息、流程事件和 Agent 回复。"
                        />
                      )}
                    </div>

                    <div className="composer-panel">
                      <Input.TextArea
                        autoSize={{ minRows: 4, maxRows: 7 }}
                        value={input}
                        onChange={(event) => setInput(event.target.value)}
                        placeholder="例如：我要做一个春节抽奖活动专题页，突出奖品、时间、门槛和视觉风格。"
                      />
                      <div className="composer-actions">
                        <Typography.Text type="secondary">
                          这里不再保留“运行提需流程”这种重复按钮。点击发送，就是完整运行一次流程。
                        </Typography.Text>
                        <Space>
                          <Button
                            disabled={!activityLog.length}
                            onClick={() => setTraceModalOpen(true)}
                          >
                            流程详情
                          </Button>
                          <Button onClick={() => setInput("")}>清空输入</Button>
                          <Button
                            type="primary"
                            loading={streaming}
                            onClick={() => void handleSubmit(input ?? "")}
                          >
                            发送
                          </Button>
                        </Space>
                      </div>
                    </div>
                    </div>
                  </div>
                </Card>

                <div className="stack-layout side-scroll-stack">
                  <Card className="panel-card" variant="outlined">
                    <div className="section-header">
                      <div>
                        <Typography.Title level={4} className="section-title">
                          对话列表
                        </Typography.Title>
                        <Typography.Text type="secondary">
                          每条对话都会保存，可切换、继续和改名。
                        </Typography.Text>
                      </div>
                      <Button onClick={handleCreateConversation}>新建对话</Button>
                    </div>

                    <div className="stack-layout compact-stack">
                      {sessionList.length ? (
                        sessionList.map((item) => (
                          <Card
                            key={item.id}
                            className="panel-card"
                            variant={item.id === session?.id ? "borderless" : "outlined"}
                            styles={{ body: { padding: 14 } }}
                            onClick={() => void handleSelectSession(item.id)}
                          >
                            <div className="stack-layout compact-stack">
                              <div className="section-header">
                                <Typography.Text strong>{item.title}</Typography.Text>
                                <Space size="small">
                                  <Tag color={item.id === session?.id ? "processing" : "default"}>
                                    {item.topic_type || "unknown"}
                                  </Tag>
                                  <Button
                                    size="small"
                                    type="text"
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      handleOpenRename(item);
                                    }}
                                  >
                                    改名
                                  </Button>
                                </Space>
                              </div>
                              <Typography.Paragraph
                                className="helper-copy"
                                ellipsis={{ rows: 2, tooltip: item.last_message_preview || "暂无消息" }}
                              >
                                {item.last_message_preview || "暂无消息"}
                              </Typography.Paragraph>
                              <div className="setting-row">
                                <span>{item.message_count} 条消息</span>
                                <span>{formatDateTime(item.updated_at)}</span>
                              </div>
                            </div>
                          </Card>
                        ))
                      ) : (
                        <Empty
                          image={Empty.PRESENTED_IMAGE_SIMPLE}
                          description="还没有历史对话，先新建一个会话。"
                        />
                      )}
                    </div>
                  </Card>

                  <Card className="panel-card" variant="outlined">
                    <Typography.Title level={4} className="section-title">
                      会话概览
                    </Typography.Title>
                    {session ? (
                      <>
                        <Progress percent={completionRatio} />
                        <Descriptions
                          className="compact-descriptions"
                          column={1}
                          items={[
                            { key: "title", label: "专题标题", children: session.title },
                            { key: "topic", label: "专题类型", children: session.topic_type },
                            {
                              key: "messages",
                              label: "消息数量",
                              children: String(session.messages.length),
                            },
                            {
                              key: "updated",
                              label: "最后更新",
                              children: formatDateTime(session.updated_at),
                            },
                          ]}
                        />
                      </>
                    ) : (
                      <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚未创建会话。" />
                    )}
                  </Card>

                  <Card className="panel-card panel-fill" variant="outlined">
                    <Typography.Title level={4} className="section-title">
                      流程追踪
                    </Typography.Title>
                    {activityLog.length ? (
                      <div className="timeline-scroll">
                        <Timeline
                          items={activityLog.map((item) => ({
                            color:
                              item.status === "failed"
                                ? "red"
                                : item.status === "running"
                                  ? "blue"
                                  : "green",
                            content: (
                              <div
                                className="timeline-item-copy"
                                role="button"
                                tabIndex={0}
                                onClick={() => {
                                  setActiveTraceId(item.trace_id);
                                  setTraceModalOpen(true);
                                }}
                                onKeyDown={(event) => {
                                  if (event.key === "Enter" || event.key === " ") {
                                    setActiveTraceId(item.trace_id);
                                    setTraceModalOpen(true);
                                  }
                                }}
                              >
                                <strong>{item.message}</strong>
                                <p>{item.detail || "系统正在处理该阶段。"}</p>
                                <p>
                                  {item.status === "failed"
                                    ? `失败：${item.error ?? "未知错误"}`
                                    : item.phase === "started"
                                      ? "节点已启动，等待输出。"
                                      : "节点已完成，可点开查看输入输出。"}
                                </p>
                                <span>{formatDateTime(item.created_at)}</span>
                              </div>
                            ),
                          }))}
                        />
                      </div>
                    ) : (
                      <Empty
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                        description="发送后，这里会出现完整的流程轨迹。"
                      />
                    )}
                  </Card>

                  <Card className="panel-card" variant="outlined">
                    <Typography.Title level={4} className="section-title">
                      检索范围与参数
                    </Typography.Title>

                    <div className="settings-stack">
                      <div className="setting-row">
                        <span>知识范围</span>
                        <span>{currentRetrieval?.document_ids?.length || "全部"}</span>
                      </div>
                      <Select
                        mode="multiple"
                        allowClear
                        value={currentRetrieval.document_ids}
                        placeholder="默认检索全部知识文档，也可以只限定某几篇。"
                        options={knowledgeDocuments.map((item) => ({
                          label: item.title,
                          value: item.id,
                        }))}
                        onChange={(value) => updateRetrieval("document_ids", value)}
                      />
                    </div>

                    <div className="settings-stack">
                      <div className="setting-row">
                        <span>候选放大倍数</span>
                        <span>{currentRetrieval.candidate_multiplier}</span>
                      </div>
                      <Slider
                        min={1}
                        max={8}
                        value={currentRetrieval.candidate_multiplier}
                        onChange={(value) =>
                          updateRetrieval("candidate_multiplier", Number(value))
                        }
                      />
                    </div>

                    <div className="settings-stack">
                      <div className="setting-row">
                        <span>召回上限 limit</span>
                        <span>{currentRetrieval.limit}</span>
                      </div>
                      <Slider
                        min={1}
                        max={12}
                        value={currentRetrieval.limit}
                        onChange={(value) => updateRetrieval("limit", Number(value))}
                      />
                    </div>

                    <div className="settings-stack">
                      <div className="setting-row">
                        <span>关键词加权</span>
                        <span>{currentRetrieval.keyword_weight.toFixed(2)}</span>
                      </div>
                      <Slider
                        min={0}
                        max={0.3}
                        step={0.01}
                        value={currentRetrieval.keyword_weight}
                        onChange={(value) =>
                          updateRetrieval("keyword_weight", Number(value))
                        }
                      />
                    </div>

                    <div className="settings-stack">
                      <div className="setting-row">
                        <span>邻接补片</span>
                        <span>{currentRetrieval.neighbor_hops}</span>
                      </div>
                      <Slider
                        min={0}
                        max={2}
                        step={1}
                        value={currentRetrieval.neighbor_hops}
                        onChange={(value) => updateRetrieval("neighbor_hops", Number(value))}
                      />
                    </div>

                    <div className="settings-stack">
                      <div className="setting-row">
                        <span>最低分阈值</span>
                        <span>{currentRetrieval.min_score.toFixed(2)}</span>
                      </div>
                      <Slider
                        min={0}
                        max={1}
                        step={0.01}
                        value={currentRetrieval.min_score}
                        onChange={(value) => updateRetrieval("min_score", Number(value))}
                      />
                    </div>

                    <div className="setting-row">
                      <span>Query Rewrite</span>
                      <Switch
                        checked={currentRetrieval.use_query_rewrite}
                        onChange={(checked) => updateRetrieval("use_query_rewrite", checked)}
                      />
                    </div>
                  </Card>
                </div>
              </div>
            ),
          },
          {
            key: "structured",
            label: "结构化结果",
            children: (
              <div className="tab-scroll-body">
                <div className="stack-layout">
                <div className="workspace-grid split-balanced">
                  <Card className="panel-card panel-fill" variant="outlined">
                    <div className="section-header">
                      <div>
                        <Typography.Title level={4} className="section-title">
                          槽位表
                        </Typography.Title>
                      </div>
                    </div>

                    <Table
                      rowKey="key"
                      size="small"
                      pagination={false}
                      scroll={{ y: 360 }}
                      dataSource={slotRows}
                      locale={{ emptyText: "会话开始后，这里会展示结构化结果。" }}
                      columns={[
                        {
                          title: "字段",
                          dataIndex: "field",
                          width: 180,
                        },
                        {
                          title: "值",
                          dataIndex: "value",
                          render: (value: string) => (
                            <Typography.Text className="multiline-cell">{value}</Typography.Text>
                          ),
                        },
                        {
                          title: "状态",
                          dataIndex: "status",
                          width: 120,
                          render: (value: string) => (
                            <Tag color={value === "已确认" ? "green" : "orange"}>{value}</Tag>
                          ),
                        },
                      ]}
                    />
                  </Card>

                  <div className="stack-layout">
                    <Card className="panel-card" variant="outlined">
                      <Typography.Title level={4} className="section-title">
                        待补字段
                      </Typography.Title>
                      <div className="tag-stack">
                        {session?.missing_slots.length ? (
                          session.missing_slots.map((slot) => (
                            <Tag key={slot} color="orange">
                              {slot}
                            </Tag>
                          ))
                        ) : (
                          <Tag color="green">核心字段已覆盖</Tag>
                        )}
                      </div>
                    </Card>

                    <Card className="panel-card" variant="outlined">
                      <Typography.Title level={4} className="section-title">
                        风险提示
                      </Typography.Title>
                      <div className="stack-layout">
                        {session?.risk_alerts.length ? (
                          session.risk_alerts.map((risk) => (
                            <InlineNotice
                              key={risk}
                              title="需要你确认"
                              description={risk}
                              tone="warning"
                            />
                          ))
                        ) : (
                          <InlineNotice
                            title="当前没有高优先级风险"
                            description="说明关键字段和规则基本自洽，可以继续进入 PRD 预览。"
                            tone="success"
                          />
                        )}
                      </div>
                    </Card>

                    <Card className="panel-card" variant="outlined">
                      <Typography.Title level={4} className="section-title">
                        使用建议
                      </Typography.Title>
                      <Typography.Paragraph className="helper-copy">
                        如果这里还有关键字段缺失，先回到“会话采集”继续补充。结构化结果稳定后，再去看 PRD 预览，会比直接盯着长文档更高效。
                      </Typography.Paragraph>
                    </Card>
                  </div>
                </div>
              </div>
              </div>
            ),
          },
          {
            key: "prd",
            label: "PRD 预览",
            children: (
              <Card className="panel-card panel-fill" variant="outlined">
                <div className="section-header">
                  <div>
                    <Typography.Title level={4} className="section-title">
                      PRD 输出
                    </Typography.Title>
                  </div>
                  <Space>
                    {session ? <Tag color="blue">{session.topic_type}</Tag> : null}
                    <Button
                      disabled={!session}
                      onClick={() =>
                        session &&
                        void exportSessionDocx(session.id, `${session.title || "专题PRD"}.docx`)
                      }
                    >
                      导出 DOCX
                    </Button>
                  </Space>
                </div>

                <div className="markdown-preview markdown-preview-fill">
                  {session?.prd_markdown ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {session.prd_markdown}
                    </ReactMarkdown>
                  ) : (
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description="完成需求采集后，这里会生成 PRD。"
                    />
                  )}
                </div>
              </Card>
            ),
          },
          {
            key: "references",
            label: "参考资料",
            children: (
              <div className="tab-scroll-body">
                <div className="stack-layout">
                <Card className="panel-card panel-fill" variant="outlined">
                  <div className="section-header">
                    <div>
                      <Typography.Title level={4} className="section-title">
                        检索命中
                      </Typography.Title>
                    </div>
                  </div>

                  <Table
                    rowKey="id"
                    pagination={false}
                    scroll={{ y: 380 }}
                    dataSource={session?.references ?? []}
                    locale={{ emptyText: "会话开始后，这里会展示命中的参考资料。" }}
                    onRow={(record) => ({
                      onClick: () => setActiveReference(record),
                    })}
                    columns={[
                      {
                        title: "预览",
                        dataIndex: "thumbnail_url",
                        width: 96,
                        render: (value: string | null | undefined, record: ReferenceCard) => (
                          <ThumbnailPreview
                            src={value}
                            alt={record.title}
                            className="thumbnail-cell"
                          />
                        ),
                      },
                      {
                        title: "标题",
                        dataIndex: "title",
                      },
                      {
                        title: "来源",
                        dataIndex: "source",
                        width: 180,
                      },
                      {
                        title: "章节路径",
                        dataIndex: "section_path",
                        width: 220,
                      },
                      {
                        title: "得分",
                        dataIndex: "score",
                        width: 100,
                        render: (value: number) => value.toFixed(3),
                      },
                      {
                        title: "摘要",
                        dataIndex: "snippet",
                        render: (value: string) => (
                          <Typography.Text className="multiline-cell">{value}</Typography.Text>
                        ),
                      },
                    ]}
                  />
                </Card>
              </div>
              </div>
            ),
          },
        ]}
      />

      <Drawer
        title={activeReference?.title ?? "参考资料详情"}
        size="large"
        open={Boolean(activeReference)}
        onClose={() => setActiveReference(null)}
      >
        {activeReference ? (
          <div className="stack-layout">
            <ThumbnailPreview
              src={activeReference.thumbnail_url}
              alt={activeReference.title}
              className="drawer-cover-image"
            />

            <Card className="panel-card" variant="outlined">
              <Descriptions
                column={1}
                items={[
                  { key: "title", label: "标题", children: activeReference.title },
                  { key: "source", label: "来源", children: activeReference.source },
                  { key: "type", label: "来源类型", children: activeReference.source_type },
                  { key: "path", label: "章节路径", children: activeReference.section_path },
                  {
                    key: "score",
                    label: "检索得分",
                    children: activeReference.score.toFixed(3),
                  },
                  {
                    key: "tags",
                    label: "标签",
                    children: activeReference.tags.length ? (
                      <div className="tag-stack">
                        {activeReference.tags.map((tag) => (
                          <Tag key={tag}>{tag}</Tag>
                        ))}
                      </div>
                    ) : (
                      "-"
                    ),
                  },
                ]}
              />
            </Card>

            <Card className="panel-card" variant="outlined">
              <Typography.Title level={5} className="section-title">
                摘要
              </Typography.Title>
              <Typography.Paragraph className="helper-copy">
                {activeReference.snippet}
              </Typography.Paragraph>
            </Card>
          </div>
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="请选择一条参考资料。" />
        )}
      </Drawer>

      <Modal
        title="修改对话名称"
        open={renameModalOpen}
        onOk={() => void handleConfirmRename()}
        onCancel={() => {
          setRenameModalOpen(false);
          setRenameSessionId("");
        }}
        okText="保存"
        cancelText="取消"
      >
        <Input
          value={renameValue}
          onChange={(event) => setRenameValue(event.target.value)}
          maxLength={120}
          placeholder="请输入新的对话标题"
        />
      </Modal>

      <Modal
        title="消息流转详情"
        open={traceModalOpen}
        onCancel={() => setTraceModalOpen(false)}
        footer={null}
        width={1080}
      >
        <div className="stack-layout">
          <div className="metric-grid metric-grid-compact">
            <Card className="panel-card" variant="outlined">
              <Progress
                percent={
                  activityLog.length
                    ? Math.round((completedTraceCount / activityLog.length) * 100)
                    : 0
                }
              />
            </Card>
            <Card className="panel-card" variant="outlined">
              <Descriptions
                size="small"
                column={1}
                className="compact-descriptions"
                items={[
                  { key: "completed", label: "已完成", children: String(completedTraceCount) },
                  { key: "running", label: "执行中", children: String(runningTraceCount) },
                  { key: "failed", label: "失败", children: String(failedTraceCount) },
                  { key: "active", label: "当前节点", children: activeTraceStep?.node ?? "-" },
                ]}
              />
            </Card>
          </div>

          <Table<TraceStep>
            rowKey="trace_id"
            size="small"
            pagination={false}
            scroll={{ y: 260 }}
            dataSource={activityLog}
            rowClassName={(record) =>
              record.trace_id === activeTraceStep?.trace_id ? "admin-table-row-selected" : ""
            }
            onRow={(record) => ({
              onClick: () => setActiveTraceId(record.trace_id),
            })}
            columns={[
              { title: "节点", dataIndex: "node", width: 120 },
              { title: "说明", dataIndex: "message", width: 180 },
              {
                title: "状态",
                key: "status",
                width: 120,
                render: (_, record) => (
                  <Tag
                    color={
                      record.status === "failed"
                        ? "error"
                        : record.status === "running"
                          ? "processing"
                          : "success"
                    }
                  >
                    {record.status}
                  </Tag>
                ),
              },
              { title: "阶段", dataIndex: "phase", width: 120 },
              {
                title: "时间",
                dataIndex: "created_at",
                width: 180,
                render: (value: string) => formatDateTime(value),
              },
              {
                title: "错误",
                dataIndex: "error",
                render: (value?: string) => value || "-",
              },
            ]}
          />

          {activeTraceStep ? (
            <Tabs
              className="admin-tabs admin-tabs-fill"
              items={[
                {
                  key: "summary",
                  label: "节点概览",
                  children: (
                    <Card className="panel-card" variant="outlined">
                      <Descriptions
                        size="small"
                        column={1}
                        className="compact-descriptions"
                        items={[
                          { key: "node", label: "节点", children: activeTraceStep.node },
                          { key: "message", label: "说明", children: activeTraceStep.message },
                          { key: "detail", label: "处理内容", children: activeTraceStep.detail || "-" },
                          { key: "phase", label: "阶段", children: activeTraceStep.phase },
                          { key: "status", label: "状态", children: activeTraceStep.status },
                          { key: "start", label: "开始时间", children: formatDateTime(activeTraceStep.started_at) },
                          { key: "end", label: "结束时间", children: formatDateTime(activeTraceStep.finished_at) },
                          { key: "error", label: "错误信息", children: activeTraceStep.error || "-" },
                        ]}
                      />
                    </Card>
                  ),
                },
                {
                  key: "input",
                  label: "输入数据",
                  children: (
                    <Card className="panel-card" variant="outlined">
                      <pre className="json-preview">{prettyTracePayload(activeTraceStep.input)}</pre>
                    </Card>
                  ),
                },
                {
                  key: "output",
                  label: "输出数据",
                  children: (
                    <Card className="panel-card" variant="outlined">
                      <pre className="json-preview">{prettyTracePayload(activeTraceStep.output)}</pre>
                    </Card>
                  ),
                },
              ]}
            />
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="发送后这里会展示完整的节点流转详情。" />
          )}
        </div>
      </Modal>
    </div>
  );
}
