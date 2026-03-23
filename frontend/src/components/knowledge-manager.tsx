"use client";

import { useEffect, useMemo, useState } from "react";

import {
  Button,
  Card,
  Descriptions,
  Drawer,
  Empty,
  Form,
  Input,
  Modal,
  Progress,
  Radio,
  Select,
  Slider,
  Space,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from "antd";
import { useInterval, useMount, useRequest } from "ahooks";

import { InlineNotice } from "@/components/inline-notice";
import { ThumbnailPreview } from "@/components/thumbnail-preview";
import {
  buildDefaultRetrievalOptions,
  createBatchReindexJob,
  createGraphRagJob,
  deleteKnowledgeDocument,
  fetchHealth,
  fetchKnowledgeDocument,
  fetchKnowledgeJob,
  listKnowledgeChunks,
  listKnowledgeDocumentVersions,
  listKnowledgeDocuments,
  listKnowledgeJobs,
  refreshKnowledge,
  reindexKnowledgeDocument,
  restoreKnowledgeDocumentVersion,
  searchKnowledge,
  updateKnowledgeDocument,
  uploadKnowledge,
} from "@/lib/api";
import type {
  HealthResponse,
  KnowledgeChunkPreview,
  KnowledgeDocumentDetail,
  KnowledgeDocumentSummary,
  KnowledgeDocumentVersionSummary,
  KnowledgeJobDetail,
  KnowledgeJobSummary,
  ReferenceCard,
  RetrievalOptions,
} from "@/lib/types";

type UploadFormValues = {
  title: string;
  source_type: string;
  source: string;
  tags?: string;
  url?: string;
  thumbnail_url?: string;
};

type EditFormValues = UploadFormValues & { content: string };

const TOPIC_OPTIONS = [
  { label: "全部主题", value: "" },
  { label: "活动专题", value: "activity" },
  { label: "展示专题", value: "display" },
  { label: "招聘专题", value: "recruitment" },
];

function formatDateTime(value?: string | null) {
  return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "-";
}

function summarizeJobType(jobType: string) {
  if (jobType === "batch_reindex") return "批量重建";
  if (jobType === "graphrag_standard") return "GraphRAG 标准构图";
  if (jobType === "graphrag_fast") return "GraphRAG 快速构图";
  return jobType;
}

function jobStatusColor(status: KnowledgeJobSummary["status"]) {
  if (status === "running") return "processing";
  if (status === "succeeded") return "success";
  if (status === "failed") return "error";
  return "default";
}

function getProgressPercent(job?: KnowledgeJobSummary | KnowledgeJobDetail | null) {
  if (!job) return 0;
  if (job.progress_total <= 0) return job.status === "succeeded" ? 100 : 0;
  return Math.min(100, Math.round((job.progress_current / job.progress_total) * 100));
}

function normalizeTags(value?: string) {
  return (value ?? "").split(",").map((item) => item.trim()).filter(Boolean);
}


function buildEditDefaults(document: KnowledgeDocumentDetail): EditFormValues {
  return {
    title: document.title,
    source_type: document.source_type,
    source: document.source,
    tags: document.tags.join(", "),
    url: document.url ?? "",
    thumbnail_url: document.thumbnail_url ?? "",
    content: document.content,
  };
}

export function KnowledgeManager() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [documents, setDocuments] = useState<KnowledgeDocumentSummary[]>([]);
  const [jobs, setJobs] = useState<KnowledgeJobSummary[]>([]);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [detailDocument, setDetailDocument] = useState<KnowledgeDocumentDetail | null>(null);
  const [detailChunks, setDetailChunks] = useState<KnowledgeChunkPreview[]>([]);
  const [detailVersions, setDetailVersions] = useState<KnowledgeDocumentVersionSummary[]>([]);
  const [activeJob, setActiveJob] = useState<KnowledgeJobDetail | null>(null);
  const [activeReference, setActiveReference] = useState<ReferenceCard | null>(null);
  const [documentDrawerOpen, setDocumentDrawerOpen] = useState(false);
  const [jobDrawerOpen, setJobDrawerOpen] = useState(false);
  const [referenceDrawerOpen, setReferenceDrawerOpen] = useState(false);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [fileInputSeed, setFileInputSeed] = useState(0);
  const [searchResults, setSearchResults] = useState<ReferenceCard[]>([]);
  const [searchDurationMs, setSearchDurationMs] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("春节 抽奖 活动 专题");
  const [searchTopicType, setSearchTopicType] = useState("");
  const [graphMethod, setGraphMethod] = useState<"standard" | "fast">("standard");
  const [apiError, setApiError] = useState("");
  const [lastRefreshAt, setLastRefreshAt] = useState("");
  const [searchRetrieval, setSearchRetrieval] = useState<RetrievalOptions>({
    ...buildDefaultRetrievalOptions(),
    use_query_rewrite: false,
  });
  const [uploadForm] = Form.useForm<UploadFormValues>();
  const [editForm] = Form.useForm<EditFormValues>();
  const [apiMessage, contextHolder] = message.useMessage();

  const dashboardRequest = useRequest(
    async () => {
      const [healthResult, documentList, jobList] = await Promise.all([
        fetchHealth(),
        listKnowledgeDocuments(),
        listKnowledgeJobs(20),
      ]);
      return { healthResult, documentList, jobList };
    },
    {
      manual: true,
      onSuccess(result) {
        setHealth(result.healthResult);
        setDocuments(result.documentList);
        setJobs(result.jobList);
        setSelectedDocumentIds((current) =>
          current.filter((id) => result.documentList.some((item) => item.id === id)),
        );
        setLastRefreshAt(new Date().toISOString());
        setApiError("");
      },
      onError(error) {
        setApiError(error.message || "知识库状态加载失败。");
      },
    },
  );

  const documentRequest = useRequest(
    async (documentId: string) => {
      const [document, chunkList, versionList] = await Promise.all([
        fetchKnowledgeDocument(documentId),
        listKnowledgeChunks(documentId),
        listKnowledgeDocumentVersions(documentId),
      ]);
      return { document, chunkList, versionList };
    },
    {
      manual: true,
      onSuccess(result) {
        setDetailDocument(result.document);
        setDetailChunks(result.chunkList);
        setDetailVersions(result.versionList);
        setDocumentDrawerOpen(true);
      },
      onError(error) {
        apiMessage.error(error.message || "加载文档详情失败。");
      },
    },
  );

  const jobRequest = useRequest(fetchKnowledgeJob, {
    manual: true,
    onSuccess(result) {
      setActiveJob(result);
      setJobDrawerOpen(true);
    },
    onError(error) {
      apiMessage.error(error.message || "加载任务详情失败。");
    },
  });

  const uploadRequest = useRequest(
    async (values: UploadFormValues) => {
      if (!uploadFile) throw new Error("请先选择一个知识文件。");
      const formData = new FormData();
      formData.append("title", values.title);
      formData.append("source_type", values.source_type);
      formData.append("source", values.source);
      formData.append("tags", values.tags ?? "");
      formData.append("url", values.url ?? "");
      formData.append("thumbnail_url", values.thumbnail_url ?? "");
      formData.append("file", uploadFile);
      return uploadKnowledge(formData);
    },
    {
      manual: true,
      onSuccess(result) {
        setUploadModalOpen(false);
        setUploadFile(null);
        setFileInputSeed((value) => value + 1);
        uploadForm.resetFields();
        apiMessage.success("知识文档已上传并入库。");
        dashboardRequest.run();
        documentRequest.run(result.id);
      },
      onError(error) {
        apiMessage.error(error.message || "上传失败。");
      },
    },
  );

  const updateRequest = useRequest(
    async (values: EditFormValues) => {
      if (!detailDocument) throw new Error("请先选择要编辑的文档。");
      return updateKnowledgeDocument(detailDocument.id, {
        title: values.title,
        source_type: values.source_type,
        source: values.source,
        tags: normalizeTags(values.tags),
        url: values.url || null,
        thumbnail_url: values.thumbnail_url || null,
        content: values.content,
      });
    },
    {
      manual: true,
      onSuccess(result) {
        setEditModalOpen(false);
        apiMessage.success("文档已更新，并生成了新版本。");
        dashboardRequest.run();
        documentRequest.run(result.id);
      },
      onError(error) {
        apiMessage.error(error.message || "更新失败。");
      },
    },
  );

  const deleteRequest = useRequest(deleteKnowledgeDocument, {
    manual: true,
    onSuccess() {
      apiMessage.success("文档已删除。");
      setDocumentDrawerOpen(false);
      setDetailDocument(null);
      setDetailChunks([]);
      setDetailVersions([]);
      dashboardRequest.run();
    },
    onError(error) {
      apiMessage.error(error.message || "删除失败。");
    },
  });

  const reindexRequest = useRequest(reindexKnowledgeDocument, {
    manual: true,
    onSuccess() {
      apiMessage.success("单文档索引已重建。");
      dashboardRequest.run();
    },
    onError(error) {
      apiMessage.error(error.message || "重建失败。");
    },
  });

  const restoreVersionRequest = useRequest(
    async (versionId: string) => {
      if (!detailDocument) throw new Error("请先打开文档详情。");
      return restoreKnowledgeDocumentVersion(detailDocument.id, versionId);
    },
    {
      manual: true,
      onSuccess(result) {
        apiMessage.success("版本已恢复。");
        dashboardRequest.run();
        documentRequest.run(result.id);
      },
      onError(error) {
        apiMessage.error(error.message || "版本恢复失败。");
      },
    },
  );

  const refreshRequest = useRequest(refreshKnowledge, {
    manual: true,
    onSuccess() {
      apiMessage.success("知识库状态已刷新。");
      dashboardRequest.run();
    },
    onError(error) {
      apiMessage.error(error.message || "刷新失败。");
    },
  });

  const batchJobRequest = useRequest(createBatchReindexJob, {
    manual: true,
    onSuccess(result) {
      apiMessage.success("批量重建任务已创建。");
      dashboardRequest.run();
      jobRequest.run(result.id);
    },
    onError(error) {
      apiMessage.error(error.message || "任务创建失败。");
    },
  });

  const graphJobRequest = useRequest(
    async (payload: { documentIds: string[]; method: "standard" | "fast" }) =>
      createGraphRagJob(payload.documentIds, payload.method),
    {
      manual: true,
      onSuccess(result) {
        apiMessage.success("GraphRAG 构图任务已创建。");
        dashboardRequest.run();
        jobRequest.run(result.id);
      },
      onError(error) {
        apiMessage.error(error.message || "GraphRAG 构图失败。");
      },
    },
  );

  const searchRequest = useRequest(
    async (payload: { query: string; topicType: string; retrieval: RetrievalOptions }) =>
      searchKnowledge(payload.query, payload.topicType, payload.retrieval),
    {
      manual: true,
      onSuccess(result) {
        setSearchResults(result);
      },
      onError(error) {
        apiMessage.error(error.message || "召回测试失败。");
      },
    },
  );

  useMount(() => {
    dashboardRequest.run();
  });

  const shouldPollJobs = useMemo(() => {
    const current = activeJob ? [activeJob] : [];
    return [...jobs, ...current].some((item) => item.status === "pending" || item.status === "running");
  }, [activeJob, jobs]);

  useInterval(
    () => {
      dashboardRequest.run();
      if (jobDrawerOpen && activeJob?.id) {
        jobRequest.run(activeJob.id);
      }
    },
    shouldPollJobs ? 4000 : undefined,
  );

  useEffect(() => {
    const listener = () => {
      void refreshRequest.runAsync();
    };
    window.addEventListener("ops:refresh:knowledge", listener);
    return () => {
      window.removeEventListener("ops:refresh:knowledge", listener);
    };
  }, [refreshRequest]);

  const builtInCount = documents.filter((item) => item.is_builtin).length;
  const managedCount = documents.filter((item) => !item.is_builtin).length;
  const runningJobCount = jobs.filter((item) => item.status === "pending" || item.status === "running").length;
  const selectedCount = selectedDocumentIds.length;
  const scopedSearchCount = searchRetrieval.document_ids.length;

  function updateSearchRetrieval<K extends keyof RetrievalOptions>(key: K, value: RetrievalOptions[K]) {
    setSearchRetrieval((current) => ({ ...(current ?? buildDefaultRetrievalOptions()), [key]: value }));
  }

  async function handleOpenDocument(documentId: string) {
    await documentRequest.runAsync(documentId);
  }

  async function handleOpenEditModal(documentId: string) {
    const result = await documentRequest.runAsync(documentId);
    editForm.setFieldsValue(buildEditDefaults(result.document));
    setEditModalOpen(true);
  }

  async function handleSearch() {
    const query = searchQuery.trim();
    if (!query) {
      apiMessage.warning("请先输入测试问题。");
      return;
    }
    const startedAt = performance.now();
    const result = await searchRequest.runAsync({ query, topicType: searchTopicType, retrieval: searchRetrieval });
    setSearchDurationMs(Math.round(performance.now() - startedAt));
    setSearchResults(result);
  }

  function confirmDeleteDocument(document: KnowledgeDocumentSummary) {
    Modal.confirm({
      title: "删除知识文档",
      content: `将永久删除《${document.title}》及其向量索引。此操作不会影响会话记录，但召回结果会立刻变化。`,
      okText: "确认删除",
      cancelText: "取消",
      okButtonProps: { danger: true },
      onOk: async () => deleteRequest.runAsync(document.id),
    });
  }

  function confirmRestoreVersion(version: KnowledgeDocumentVersionSummary) {
    Modal.confirm({
      title: "恢复历史版本",
      content: `将《${version.title}》恢复到 V${version.version_number}，当前版本会保留在历史记录中。`,
      okText: "确认恢复",
      cancelText: "取消",
      onOk: async () => restoreVersionRequest.runAsync(version.id),
    });
  }

  const documentColumns = [
    {
      title: "预览",
      dataIndex: "thumbnail_url",
      width: 88,
      render: (_: string | null | undefined, record: KnowledgeDocumentSummary) => (
        <div className="thumbnail-cell">
          <ThumbnailPreview src={record.thumbnail_url} alt={record.title} />
        </div>
      ),
    },
    {
      title: "标题 / 状态",
      dataIndex: "title",
      render: (value: string, record: KnowledgeDocumentSummary) => (
        <div className="compact-stack">
          <Typography.Text strong>{value}</Typography.Text>
          <Space wrap size={[6, 6]}>
            <Tag color={record.is_builtin ? "gold" : "blue"}>{record.is_builtin ? "内置基线" : "托管文档"}</Tag>
            <Tag>{record.source_type}</Tag>
            {record.tags.slice(0, 3).map((tag) => <Tag key={tag}>{tag}</Tag>)}
          </Space>
        </div>
      ),
    },
    { title: "来源", dataIndex: "source", width: 180 },
    { title: "切片数", dataIndex: "chunk_count", width: 96 },
    { title: "更新时间", dataIndex: "updated_at", width: 180, render: formatDateTime },
    {
      title: "操作",
      key: "actions",
      width: 250,
      render: (_: unknown, record: KnowledgeDocumentSummary) => (
        <Space wrap size={[8, 8]}>
          <Button size="small" onClick={(event) => { event.stopPropagation(); void handleOpenDocument(record.id); }}>查看</Button>
          <Button size="small" loading={reindexRequest.loading} onClick={(event) => { event.stopPropagation(); void reindexRequest.runAsync(record.id); }}>重建索引</Button>
          {!record.is_builtin ? <Button size="small" onClick={(event) => { event.stopPropagation(); void handleOpenEditModal(record.id); }}>编辑</Button> : null}
          {!record.is_builtin ? <Button size="small" danger onClick={(event) => { event.stopPropagation(); confirmDeleteDocument(record); }}>删除</Button> : null}
        </Space>
      ),
    },
  ];

  const jobColumns = [
    { title: "任务类型", dataIndex: "job_type", render: summarizeJobType },
    { title: "状态", dataIndex: "status", width: 110, render: (value: KnowledgeJobSummary["status"]) => <Tag color={jobStatusColor(value)}>{value}</Tag> },
    { title: "进度", key: "progress", width: 180, render: (_: unknown, record: KnowledgeJobSummary) => <Progress percent={getProgressPercent(record)} size="small" /> },
    { title: "更新时间", dataIndex: "updated_at", width: 180, render: formatDateTime },
    { title: "操作", key: "actions", width: 100, render: (_: unknown, record: KnowledgeJobSummary) => <Button size="small" onClick={(event) => { event.stopPropagation(); void jobRequest.runAsync(record.id); }}>详情</Button> },
  ];

  const searchColumns = [
    {
      title: "预览",
      dataIndex: "thumbnail_url",
      width: 88,
      render: (_: string | null | undefined, record: ReferenceCard) => (
        <div className="thumbnail-cell">
          <ThumbnailPreview src={record.thumbnail_url} alt={record.title} />
        </div>
      ),
    },
    { title: "标题", dataIndex: "title", width: 180 },
    { title: "来源", dataIndex: "source", width: 160 },
    { title: "章节", dataIndex: "section_path", width: 180 },
    { title: "分数", dataIndex: "score", width: 100, render: (value: number) => value.toFixed(3) },
    { title: "摘要", dataIndex: "snippet", render: (value: string) => <Typography.Paragraph className="helper-copy" ellipsis={{ rows: 3, tooltip: value }}>{value}</Typography.Paragraph> },
  ];

  return (
    <div className="page-stack console-page">
      {contextHolder}

      <div className="page-toolbar">
        <Space wrap>
          <Button type="primary" onClick={() => setUploadModalOpen(true)}>上传文档</Button>
        </Space>
      </div>

      {apiError ? <InlineNotice title="知识库连接异常" description={apiError} tone="error" /> : null}

      <div className="metric-grid metric-grid-compact">
        <Card className="panel-card" variant="outlined"><Statistic title="知识文档总数" value={documents.length} /></Card>
        <Card className="panel-card" variant="outlined"><Statistic title="切片总数" value={health?.knowledge_chunks ?? 0} /></Card>
        <Card className="panel-card metric-text-card" variant="outlined">
          <Typography.Text type="secondary">最近刷新</Typography.Text>
          <Typography.Title level={3} className="metric-text-value">
            {lastRefreshAt ? formatDateTime(lastRefreshAt) : "-"}
          </Typography.Title>
        </Card>
      </div>

      <Tabs className="admin-tabs admin-tabs-fill" items={[
        {
          key: "documents",
          label: "文档中心",
          children: (
            <div className="tab-scroll-body">
              <div className="stack-layout">
                <Card className="panel-card" variant="outlined">
                  <div className="section-header">
                    <div>
                      <Typography.Title level={4} className="section-title">文档台账</Typography.Title>
                    </div>
                    <Space wrap><Tag color="blue">内置 {builtInCount}</Tag><Tag color="processing">托管 {managedCount}</Tag></Space>
                  </div>

                  <Table
                    rowKey="id"
                    size="middle"
                    pagination={{ pageSize: 8, showSizeChanger: false }}
                    rowSelection={{ selectedRowKeys: selectedDocumentIds, onChange: (keys) => setSelectedDocumentIds(keys as string[]) }}
                    dataSource={documents}
                    columns={documentColumns}
                    locale={{ emptyText: "暂无知识文档。" }}
                    onRow={(record) => ({ onClick: () => { void handleOpenDocument(record.id); } })}
                  />
                </Card>
              </div>
            </div>
          ),
        },
        {
          key: "jobs",
          label: "任务中心",
          children: (
            <div className="tab-scroll-body">
              <div className="stack-layout">
                <div className="feature-grid knowledge-action-grid">
                  <Card className="panel-card" variant="outlined">
                    <div className="stack-layout compact-stack">
                      <Typography.Title level={5} className="section-title">批量重建向量索引</Typography.Title>
                      <Tag color={selectedCount ? "processing" : "default"}>{selectedCount ? `当前选中 ${selectedCount} 篇` : "请先在文档中心勾选文档"}</Tag>
                      <Button type="primary" disabled={!selectedCount} loading={batchJobRequest.loading} onClick={() => void batchJobRequest.runAsync(selectedDocumentIds)}>创建批量重建任务</Button>
                    </div>
                  </Card>

                  <Card className="panel-card" variant="outlined">
                    <div className="stack-layout compact-stack">
                      <Typography.Title level={5} className="section-title">GraphRAG 构图</Typography.Title>
                      <Typography.Paragraph className="helper-copy">GraphRAG 索引就在这里创建。构图完成后，再去图谱查询页选择该索引执行问答和关系分析。</Typography.Paragraph>
                      <Radio.Group
                        value={graphMethod}
                        optionType="button"
                        buttonStyle="solid"
                        onChange={(event) => setGraphMethod(event.target.value)}
                        options={[{ label: "标准模式", value: "standard" }, { label: "快速模式", value: "fast" }]}
                      />
                      <Button disabled={!selectedCount} loading={graphJobRequest.loading} onClick={() => void graphJobRequest.runAsync({ documentIds: selectedDocumentIds, method: graphMethod })}>创建 GraphRAG 构图任务</Button>
                    </div>
                  </Card>

                  <Card className="panel-card" variant="outlined">
                    <div className="stack-layout compact-stack">
                      <Typography.Title level={5} className="section-title">当前运行概览</Typography.Title>
                      <Descriptions column={1} size="small" className="compact-descriptions">
                        <Descriptions.Item label="运行中任务">{runningJobCount} 个</Descriptions.Item>
                      </Descriptions>
                    </div>
                  </Card>
                </div>

                <Card className="panel-card" variant="outlined">
                  <div className="section-header">
                    <div>
                      <Typography.Title level={4} className="section-title">任务流水</Typography.Title>
                      <Typography.Text type="secondary">点开任意任务即可查看进度、输入文档和产物摘要。运行中的任务会自动轮询刷新。</Typography.Text>
                    </div>
                  </div>
                  <Table rowKey="id" size="middle" pagination={{ pageSize: 8, showSizeChanger: false }} dataSource={jobs} columns={jobColumns} locale={{ emptyText: "暂无任务记录。" }} onRow={(record) => ({ onClick: () => { void jobRequest.runAsync(record.id); } })} />
                </Card>
              </div>
            </div>
          ),
        },
        {
          key: "search",
          label: "召回测试",
          children: (
            <div className="tab-scroll-body">
              <div className="stack-layout">
                <div className="workspace-grid split-balanced">
                  <Card className="panel-card panel-fill" variant="outlined">
                    <div className="section-header">
                      <div>
                        <Typography.Title level={4} className="section-title">检索参数配置</Typography.Title>
                      </div>
                      <Button type="primary" loading={searchRequest.loading} onClick={() => void handleSearch()}>执行召回测试</Button>
                    </div>

                    <div className="stack-layout side-scroll-stack">
                      <Input.TextArea value={searchQuery} rows={4} placeholder="例如：春节活动页面需要强调哪些规则和按钮文案？" onChange={(event) => setSearchQuery(event.target.value)} />
                      <Select value={searchTopicType} options={TOPIC_OPTIONS} onChange={setSearchTopicType} />
                      <div className="settings-stack">
                        <div className="setting-row"><span>文档范围</span><span>{scopedSearchCount ? `已限定 ${scopedSearchCount} 篇` : "全部文档"}</span></div>
                        <Select mode="multiple" allowClear value={searchRetrieval.document_ids} placeholder="默认检索全部知识文档，也可以只限定某几篇。" options={documents.map((item) => ({ label: `${item.title}${item.is_builtin ? "（内置）" : ""}`, value: item.id }))} onChange={(value) => updateSearchRetrieval("document_ids", value)} />
                      </div>
                      <div className="settings-stack"><div className="setting-row"><span>limit</span><span>{searchRetrieval.limit}</span></div><Slider min={1} max={10} value={searchRetrieval.limit} onChange={(value) => updateSearchRetrieval("limit", value)} /></div>
                      <div className="settings-stack"><div className="setting-row"><span>candidate multiplier</span><span>{searchRetrieval.candidate_multiplier}</span></div><Slider min={1} max={8} value={searchRetrieval.candidate_multiplier} onChange={(value) => updateSearchRetrieval("candidate_multiplier", value)} /></div>
                      <div className="settings-stack"><div className="setting-row"><span>keyword weight</span><span>{searchRetrieval.keyword_weight.toFixed(2)}</span></div><Slider min={0} max={0.5} step={0.01} value={searchRetrieval.keyword_weight} onChange={(value) => updateSearchRetrieval("keyword_weight", value)} /></div>
                      <div className="settings-stack"><div className="setting-row"><span>neighbor hops</span><span>{searchRetrieval.neighbor_hops}</span></div><Slider min={0} max={3} value={searchRetrieval.neighbor_hops} onChange={(value) => updateSearchRetrieval("neighbor_hops", value)} /></div>
                      <div className="settings-stack"><div className="setting-row"><span>min score</span><span>{searchRetrieval.min_score.toFixed(2)}</span></div><Slider min={0} max={0.8} step={0.01} value={searchRetrieval.min_score} onChange={(value) => updateSearchRetrieval("min_score", value)} /></div>
                      <div className="settings-stack">
                        <div className="setting-row"><span>Query Rewrite</span><Tag color={searchRetrieval.use_query_rewrite ? "processing" : "default"}>{searchRetrieval.use_query_rewrite ? "已开启" : "已关闭"}</Tag></div>
                        <Radio.Group value={searchRetrieval.use_query_rewrite} optionType="button" buttonStyle="solid" onChange={(event) => updateSearchRetrieval("use_query_rewrite", event.target.value)} options={[{ label: "关闭", value: false }, { label: "开启", value: true }]} />
                      </div>
                    </div>
                  </Card>

                  <Card className="panel-card panel-fill" variant="outlined">
                    <div className="section-header">
                      <div>
                        <Typography.Title level={4} className="section-title">检索命中</Typography.Title>
                        <Typography.Text type="secondary">结果都来自原始知识文档切片，不是我临时生成的文本。点击行可展开查看摘要、标签和来源链接。</Typography.Text>
                      </div>
                      <Space wrap><Tag color="blue">{searchResults.length} 条命中</Tag>{searchDurationMs != null ? <Tag color="processing">{searchDurationMs} ms</Tag> : null}</Space>
                    </div>
                    <Table rowKey="id" size="small" pagination={{ pageSize: 6, showSizeChanger: false }} scroll={{ y: 430 }} dataSource={searchResults} columns={searchColumns} locale={{ emptyText: "执行测试后，这里会显示检索命中。" }} onRow={(record) => ({ onClick: () => { setActiveReference(record); setReferenceDrawerOpen(true); } })} />
                  </Card>
                </div>
              </div>
            </div>
          ),
        },
      ]} />

      <Drawer size="large" open={documentDrawerOpen} onClose={() => setDocumentDrawerOpen(false)} title={detailDocument ? `文档详情 · ${detailDocument.title}` : "文档详情"}>
        {detailDocument ? (
          <div className="stack-layout">
            <InlineNotice
              title={detailDocument.is_builtin ? "这是内置基线文档" : "这是托管知识文档"}
              description={detailDocument.is_builtin ? "内置文档用于提供开箱即用的知识样本，一般只查看和重建索引，不建议当作业务文档直接维护。" : "托管文档可以编辑、恢复版本和删除。聊天输出不会自动写回这篇文档。"}
              tone={detailDocument.is_builtin ? "warning" : "info"}
            />
            <Descriptions column={1} size="small" className="compact-descriptions">
              <Descriptions.Item label="标题">{detailDocument.title}</Descriptions.Item>
              <Descriptions.Item label="来源">{detailDocument.source}</Descriptions.Item>
              <Descriptions.Item label="类型">{detailDocument.source_type}</Descriptions.Item>
              <Descriptions.Item label="原始文件">{detailDocument.origin_file_name ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="对象存储 Key">{detailDocument.storage_key ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="更新时间">{formatDateTime(detailDocument.updated_at)}</Descriptions.Item>
            </Descriptions>
            <Tabs items={[
              { key: "content", label: "正文预览", children: <Card className="panel-card" variant="outlined"><Typography.Paragraph className="drawer-pre-wrap">{detailDocument.content}</Typography.Paragraph></Card> },
              { key: "chunks", label: `切片预览（${detailChunks.length}）`, children: <Table rowKey="id" size="small" pagination={{ pageSize: 5, showSizeChanger: false }} dataSource={detailChunks} locale={{ emptyText: "暂无切片。" }} columns={[{ title: "序号", dataIndex: "chunk_index", width: 80 }, { title: "章节", dataIndex: "section_path", width: 200 }, { title: "内容", dataIndex: "content", render: (value: string) => <Typography.Paragraph className="helper-copy" ellipsis={{ rows: 3, tooltip: value }}>{value}</Typography.Paragraph> }]} /> },
              { key: "versions", label: `版本记录（${detailVersions.length}）`, children: <Table rowKey="id" size="small" pagination={{ pageSize: 5, showSizeChanger: false }} dataSource={detailVersions} locale={{ emptyText: "暂无版本记录。" }} columns={[{ title: "版本", dataIndex: "version_number", width: 80, render: (value: number) => `V${value}` }, { title: "标题", dataIndex: "title" }, { title: "时间", dataIndex: "created_at", width: 180, render: formatDateTime }, { title: "操作", key: "actions", width: 120, render: (_: unknown, record: KnowledgeDocumentVersionSummary) => <Button size="small" onClick={() => confirmRestoreVersion(record)}>恢复此版本</Button> }]} /> },
            ]} />
          </div>
        ) : <Empty description="请选择一篇文档查看详情。" />}
      </Drawer>

      <Drawer size="large" open={jobDrawerOpen} onClose={() => setJobDrawerOpen(false)} title={activeJob ? summarizeJobType(activeJob.job_type) : "任务详情"}>
        {activeJob ? (
          <div className="stack-layout">
            <InlineNotice title="任务说明" description={activeJob.job_type.startsWith("graphrag") ? "GraphRAG 构图任务会为已选文档生成图谱索引和相关产物，成功后才能在图谱查询页选择该索引。" : "重建任务会重新切片、重新 embedding 并刷新混合检索索引。"} />
            <Descriptions column={1} size="small" className="compact-descriptions">
              <Descriptions.Item label="任务类型">{summarizeJobType(activeJob.job_type)}</Descriptions.Item>
              <Descriptions.Item label="Provider">{activeJob.provider}</Descriptions.Item>
              <Descriptions.Item label="状态"><Tag color={jobStatusColor(activeJob.status)}>{activeJob.status}</Tag></Descriptions.Item>
              <Descriptions.Item label="文档数">{activeJob.document_ids.length}</Descriptions.Item>
              <Descriptions.Item label="开始时间">{formatDateTime(activeJob.started_at)}</Descriptions.Item>
              <Descriptions.Item label="结束时间">{formatDateTime(activeJob.finished_at)}</Descriptions.Item>
              <Descriptions.Item label="错误信息">{activeJob.error_message ?? "-"}</Descriptions.Item>
            </Descriptions>
            <Card className="panel-card" variant="outlined"><Typography.Title level={5} className="section-title">执行进度</Typography.Title><Progress percent={getProgressPercent(activeJob)} /></Card>
            <Card className="panel-card" variant="outlined"><Typography.Title level={5} className="section-title">任务产物</Typography.Title><pre className="json-preview">{JSON.stringify(activeJob.result ?? {}, null, 2)}</pre></Card>
          </div>
        ) : <Empty description="请选择一条任务查看详情。" />}
      </Drawer>

      <Drawer size="large" open={referenceDrawerOpen} onClose={() => setReferenceDrawerOpen(false)} title={activeReference ? activeReference.title : "检索命中详情"}>
        {activeReference ? (
          <div className="stack-layout">
            <div className="reference-preview-large"><ThumbnailPreview src={activeReference.thumbnail_url} alt={activeReference.title} /></div>
            <Descriptions column={1} size="small" className="compact-descriptions">
              <Descriptions.Item label="来源">{activeReference.source}</Descriptions.Item>
              <Descriptions.Item label="章节">{activeReference.section_path || "-"}</Descriptions.Item>
              <Descriptions.Item label="相似度">{activeReference.score.toFixed(3)}</Descriptions.Item>
              <Descriptions.Item label="标签"><Space wrap size={[6, 6]}>{activeReference.tags.map((tag) => <Tag key={tag}>{tag}</Tag>)}</Space></Descriptions.Item>
              <Descriptions.Item label="链接">{activeReference.url ? <a href={activeReference.url} target="_blank" rel="noreferrer">{activeReference.url}</a> : "-"}</Descriptions.Item>
            </Descriptions>
            <Card className="panel-card" variant="outlined"><Typography.Paragraph className="drawer-pre-wrap">{activeReference.snippet}</Typography.Paragraph></Card>
          </div>
        ) : <Empty description="请选择一条命中查看详情。" />}
      </Drawer>

      <Modal open={uploadModalOpen} width={760} title="上传知识文档" okText="上传并入库" cancelText="取消" confirmLoading={uploadRequest.loading} onCancel={() => setUploadModalOpen(false)} onOk={() => uploadForm.submit()}>
        <div className="stack-layout">
          <InlineNotice title="支持什么文件" description="支持 .md / .txt / .docx，系统会自动切片入库。source 用来标记来源系统，thumbnail_url 是可选的缩略图地址。" />
          <Form form={uploadForm} layout="vertical" onFinish={(values) => uploadRequest.run(values)}>
            <Form.Item name="title" label="文档标题" rules={[{ required: true, message: "请输入标题" }]}><Input placeholder="例如：春节抽奖活动模板" /></Form.Item>
            <Form.Item name="source_type" label="来源类型" rules={[{ required: true, message: "请输入来源类型" }]}><Input placeholder="例如：运营模板库 / 埋点规范库 / 设计规范库" /></Form.Item>
            <Form.Item name="source" label="来源标识" rules={[{ required: true, message: "请输入来源标识" }]}><Input placeholder="例如：topic_ops_manual / campaign_template_repo" /></Form.Item>
            <Form.Item name="tags" label="标签"><Input placeholder="多个标签用英文逗号分隔，例如：activity, spring, lottery" /></Form.Item>
            <Form.Item name="url" label="外部链接"><Input placeholder="可选，用于保留原始文档链接" /></Form.Item>
            <Form.Item name="thumbnail_url" label="缩略图链接"><Input placeholder="可选，若失效会自动显示占位卡片" /></Form.Item>
            <Form.Item label="知识文件" required><input key={fileInputSeed} type="file" accept=".md,.txt,.docx" onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)} /></Form.Item>
          </Form>
        </div>
      </Modal>

      <Modal open={editModalOpen} width={920} title="编辑知识文档" okText="保存并生成新版本" cancelText="取消" confirmLoading={updateRequest.loading} onCancel={() => setEditModalOpen(false)} onOk={() => editForm.submit()}>
        <div className="stack-layout">
          <InlineNotice title="编辑会发生什么" description="保存后会生成新的文档版本，并同步重建该文档的切片和向量索引。你可以在文档详情里的版本记录中恢复历史版本。" />
          <Form form={editForm} layout="vertical" onFinish={(values) => updateRequest.run(values)}>
            <div className="form-grid">
              <Form.Item name="title" label="文档标题" rules={[{ required: true, message: "请输入标题" }]}><Input /></Form.Item>
              <Form.Item name="source_type" label="来源类型" rules={[{ required: true, message: "请输入来源类型" }]}><Input /></Form.Item>
            </div>
            <div className="form-grid">
              <Form.Item name="source" label="来源标识" rules={[{ required: true, message: "请输入来源标识" }]}><Input /></Form.Item>
              <Form.Item name="tags" label="标签"><Input /></Form.Item>
            </div>
            <div className="form-grid">
              <Form.Item name="url" label="外部链接"><Input /></Form.Item>
              <Form.Item name="thumbnail_url" label="缩略图链接"><Input /></Form.Item>
            </div>
            <Form.Item name="content" label="正文内容" rules={[{ required: true, message: "请输入正文内容" }]}><Input.TextArea rows={16} /></Form.Item>
          </Form>
        </div>
      </Modal>
    </div>
  );
}
