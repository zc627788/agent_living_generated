"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  Button,
  Card,
  Descriptions,
  Empty,
  Input,
  Progress,
  Radio,
  Slider,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from "antd";
import { useMount, useRequest } from "ahooks";

import { InlineNotice } from "@/components/inline-notice";
import { listGraphIndexes, queryGraph } from "@/lib/api";
import type {
  GraphCommunityReport,
  GraphEdge,
  GraphIndexSummary,
  GraphNode,
  GraphQueryResponse,
} from "@/lib/types";

function buildNodeLayout(nodes: GraphNode[]) {
  const width = 860;
  const height = 520;
  const centerX = width / 2;
  const centerY = height / 2;
  const positions: Record<string, { x: number; y: number }> = {};

  if (!nodes.length) {
    return positions;
  }

  positions[nodes[0].id] = { x: centerX, y: centerY };
  const rest = nodes.slice(1);
  rest.forEach((node, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(rest.length, 1);
    const radius = 150 + (index % 2) * 60;
    positions[node.id] = {
      x: centerX + Math.cos(angle) * radius,
      y: centerY + Math.sin(angle) * radius,
    };
  });

  return positions;
}

function formatDateTime(value?: string | null) {
  return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "-";
}

export function GraphExplorer() {
  const [indexes, setIndexes] = useState<GraphIndexSummary[]>([]);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [query, setQuery] = useState("这个专题页的关键负责人与风险关系是什么？");
  const [mode, setMode] = useState<"local" | "global">("local");
  const [entityLimit, setEntityLimit] = useState(12);
  const [edgeLimit, setEdgeLimit] = useState(20);
  const [communityLimit, setCommunityLimit] = useState(3);
  const [result, setResult] = useState<GraphQueryResponse | null>(null);
  const [apiMessage, contextHolder] = message.useMessage();

  const indexesRequest = useRequest(() => listGraphIndexes(20), {
    manual: true,
    onSuccess(data) {
      setIndexes(data);
      if (!selectedJobId && data.length) {
        setSelectedJobId(data[0].job_id);
      }
    },
    onError(error) {
      apiMessage.error(error.message || "加载图谱索引失败。");
    },
  });

  const queryRequest = useRequest(
    async () => {
      if (!selectedJobId) {
        throw new Error("暂无可用图谱索引，请先去知识库的任务中心创建构图任务。");
      }
      if (!query.trim()) {
        throw new Error("请先输入查询问题。");
      }
      return queryGraph({
        job_id: selectedJobId,
        query: query.trim(),
        mode,
        entity_limit: entityLimit,
        edge_limit: edgeLimit,
        community_limit: communityLimit,
      });
    },
    {
      manual: true,
      onSuccess(data) {
        setResult(data);
      },
      onError(error) {
        apiMessage.error(error.message || "图谱查询失败。");
      },
    },
  );

  useMount(() => {
    indexesRequest.run();
  });

  useEffect(() => {
    const listener = () => {
      void indexesRequest.runAsync().then(() => {
        apiMessage.success("图谱索引已刷新。");
      });
    };
    window.addEventListener("ops:refresh:graph", listener);
    return () => {
      window.removeEventListener("ops:refresh:graph", listener);
    };
  }, [apiMessage, indexesRequest]);

  const positions = buildNodeLayout(result?.nodes ?? []);
  const selectedIndex = indexes.find((item) => item.job_id === selectedJobId) ?? null;

  return (
    <div className="page-stack console-page">
      {contextHolder}

      <div className="page-toolbar"></div>

      <div className="metric-grid">
        <Card className="panel-card" variant="outlined">
          <Statistic title="可用索引" value={indexes.length} />
        </Card>
        <Card className="panel-card" variant="outlined">
          <Statistic title="当前实体数" value={result?.nodes.length ?? 0} />
        </Card>
        <Card className="panel-card" variant="outlined">
          <Statistic title="当前关系数" value={result?.edges.length ?? 0} />
        </Card>
        <Card className="panel-card" variant="outlined">
          <Statistic title="社区报告数" value={result?.reports.length ?? 0} />
        </Card>
      </div>

      <div className="workspace-grid graph-grid">
        <div className="stack-layout side-scroll-stack">
          <Card className="panel-card panel-fill" variant="outlined">
            <div className="section-header">
              <div>
                <Typography.Title level={4} className="section-title">
                  图谱索引列表
                </Typography.Title>
              </div>
            </div>

            <Table
              rowKey="job_id"
              size="small"
              pagination={false}
              scroll={{ y: 280 }}
              dataSource={indexes}
              locale={{ emptyText: "暂无可用的图谱索引。" }}
              rowClassName={(record) =>
                record.job_id === selectedJobId ? "admin-table-row-selected" : ""
              }
              onRow={(record) => ({
                onClick: () => setSelectedJobId(record.job_id),
              })}
              columns={[
                {
                  title: "方法",
                  dataIndex: "method",
                  width: 120,
                  render: (value: string) => <Tag color="blue">{value}</Tag>,
                },
                {
                  title: "文档",
                  dataIndex: "document_titles",
                  render: (value: string[]) => (
                    <div className="tag-stack">
                      {value.slice(0, 2).map((title) => (
                        <Tag key={title}>{title}</Tag>
                      ))}
                      {value.length > 2 ? <Tag>+{value.length - 2}</Tag> : null}
                    </div>
                  ),
                },
                {
                  title: "创建时间",
                  dataIndex: "created_at",
                  width: 180,
                  render: (value: string) => formatDateTime(value),
                },
              ]}
            />
          </Card>

          <Card className="panel-card" variant="outlined">
            <Typography.Title level={4} className="section-title">
              查询配置
            </Typography.Title>

            <div className="stack-layout">
              <Input.TextArea
                autoSize={{ minRows: 4, maxRows: 6 }}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="例如：这个专题页的关键负责人与风险关系是什么？"
              />

              <div className="setting-row">
                <span>查询模式</span>
                <Radio.Group
                  value={mode}
                  onChange={(event) => setMode(event.target.value)}
                  optionType="button"
                  buttonStyle="solid"
                >
                  <Radio.Button value="local">local</Radio.Button>
                  <Radio.Button value="global">global</Radio.Button>
                </Radio.Group>
              </div>

              <div className="settings-stack">
                <div className="setting-row">
                  <span>实体上限</span>
                  <span>{entityLimit}</span>
                </div>
                <Slider
                  min={3}
                  max={40}
                  value={entityLimit}
                  onChange={(value) => setEntityLimit(Number(value))}
                />
              </div>

              <div className="settings-stack">
                <div className="setting-row">
                  <span>关系上限</span>
                  <span>{edgeLimit}</span>
                </div>
                <Slider
                  min={0}
                  max={80}
                  value={edgeLimit}
                  onChange={(value) => setEdgeLimit(Number(value))}
                />
              </div>

              <div className="settings-stack">
                <div className="setting-row">
                  <span>社区报告上限</span>
                  <span>{communityLimit}</span>
                </div>
                <Slider
                  min={0}
                  max={10}
                  value={communityLimit}
                  onChange={(value) => setCommunityLimit(Number(value))}
                />
              </div>

              <Button
                type="primary"
                disabled={!selectedJobId}
                loading={queryRequest.loading}
                onClick={() => queryRequest.run()}
              >
                执行查询
              </Button>
            </div>
          </Card>

          <Card className="panel-card" variant="outlined">
            <Typography.Title level={4} className="section-title">
              当前索引说明
            </Typography.Title>

            {selectedIndex ? (
              <Descriptions
                column={1}
                items={[
                  { key: "method", label: "构图方法", children: selectedIndex.method },
                  {
                    key: "created_at",
                    label: "创建时间",
                    children: formatDateTime(selectedIndex.created_at),
                  },
                  {
                    key: "documents",
                    label: "文档数量",
                    children: String(selectedIndex.document_titles.length),
                  },
                  {
                    key: "workspace",
                    label: "工作目录",
                    children: selectedIndex.workspace_dir ?? "-",
                  },
                ]}
              />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="请选择一个索引。" />
            )}
          </Card>
        </div>

        <Card className="panel-card panel-fill" variant="outlined">
          <Tabs
            className="admin-tabs admin-tabs-fill"
            items={[
              {
                key: "answer",
                label: "查询回答",
                children: result ? (
                  <div className="stack-layout tab-scroll-body">
                    <InlineNotice
                      title="Query Rewrite"
                      description={result.rewritten_query || "当前未启用重写。"}
                    />
                    <div className="graph-answer-box">{result.answer}</div>
                    <div className="metric-grid metric-grid-compact">
                      {Object.entries(result.artifacts).map(([key, value]) => (
                        <Card key={key} className="panel-card" variant="outlined">
                          <Statistic title={key} value={value} />
                        </Card>
                      ))}
                    </div>
                  </div>
                ) : (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="先选择一个索引，再执行查询，这里会显示图谱问答结果。"
                  />
                ),
              },
              {
                key: "graph",
                label: "关系图",
                children: result?.nodes.length ? (
                  <div className="stack-layout tab-scroll-body">
                    <div className="graph-canvas">
                      <svg viewBox="0 0 860 520" className="graph-svg" aria-label="graph">
                        {result.edges.map((edge) => {
                          const source = positions[edge.source];
                          const target = positions[edge.target];
                          if (!source || !target) {
                            return null;
                          }
                          return (
                            <line
                              key={`${edge.source}-${edge.target}-${edge.weight}`}
                              x1={source.x}
                              y1={source.y}
                              x2={target.x}
                              y2={target.y}
                              stroke="rgba(37, 99, 235, 0.28)"
                              strokeWidth={Math.max(1, edge.weight / 8)}
                            />
                          );
                        })}
                      </svg>

                      {result.nodes.map((node) => {
                        const position = positions[node.id];
                        if (!position) {
                          return null;
                        }
                        return (
                          <div
                            key={node.id}
                            className="graph-node"
                            style={{
                              left: `${position.x}px`,
                              top: `${position.y}px`,
                              width: `${88 + node.size * 10}px`,
                            }}
                          >
                            <strong>{node.label}</strong>
                            <span>{node.kind}</span>
                          </div>
                        );
                      })}
                    </div>

                    <div className="workspace-grid split-equal">
                      <Table<GraphNode>
                        rowKey="id"
                        size="small"
                        pagination={false}
                        scroll={{ y: 240 }}
                        dataSource={result.nodes}
                        columns={[
                          { title: "实体", dataIndex: "label" },
                          { title: "类型", dataIndex: "kind", width: 120 },
                          {
                            title: "分数",
                            dataIndex: "score",
                            width: 100,
                            render: (value: number) => value.toFixed(3),
                          },
                        ]}
                      />

                      <Table<GraphEdge>
                        rowKey={(record) =>
                          `${record.source}-${record.target}-${record.label ?? "edge"}`
                        }
                        size="small"
                        pagination={false}
                        scroll={{ y: 240 }}
                        dataSource={result.edges}
                        columns={[
                          { title: "Source", dataIndex: "source" },
                          { title: "Target", dataIndex: "target" },
                          {
                            title: "Weight",
                            dataIndex: "weight",
                            width: 100,
                            render: (value: number) => value.toFixed(2),
                          },
                        ]}
                      />
                    </div>
                  </div>
                ) : (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="执行一次查询后，这里会展示实体关系图。"
                  />
                ),
              },
              {
                key: "reports",
                label: "社区报告",
                children: result?.reports.length ? (
                  <Table<GraphCommunityReport>
                    rowKey="id"
                    pagination={false}
                    scroll={{ y: 480 }}
                    dataSource={result.reports}
                    columns={[
                      {
                        title: "标题",
                        dataIndex: "title",
                      },
                      {
                        title: "排名",
                        dataIndex: "rank",
                        width: 100,
                        render: (value: number) => <Tag color="gold">{value.toFixed(2)}</Tag>,
                      },
                      {
                        title: "摘要",
                        dataIndex: "summary",
                        render: (value: string) => (
                          <Typography.Text className="multiline-cell">{value}</Typography.Text>
                        ),
                      },
                    ]}
                  />
                ) : (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无社区报告命中。" />
                ),
              },
              {
                key: "assets",
                label: "索引资产",
                children: selectedIndex ? (
                  <div className="stack-layout tab-scroll-body">
                    <Card className="panel-card" variant="outlined">
                      <Descriptions
                        column={1}
                        items={[
                          {
                            key: "workspace_dir",
                            label: "workspace_dir",
                            children: selectedIndex.workspace_dir ?? "-",
                          },
                          {
                            key: "graphml_path",
                            label: "graphml_path",
                            children: selectedIndex.graphml_path ?? "-",
                          },
                        ]}
                      />
                    </Card>

                    <div className="metric-grid metric-grid-compact">
                      {Object.entries(selectedIndex.artifact_counts).map(([key, value]) => (
                        <Card key={key} className="panel-card" variant="outlined">
                          <Statistic title={key} value={value} />
                          <Progress
                            percent={Math.min(100, Math.max(8, Math.round((value / 100) * 100)))}
                            showInfo={false}
                            size="small"
                          />
                        </Card>
                      ))}
                    </div>
                  </div>
                ) : (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="请选择一个索引。" />
                ),
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
