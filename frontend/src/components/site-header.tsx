"use client";

// 顶部栏负责告诉用户“当前在哪个模块、这个模块是干什么的”。

import { usePathname } from "next/navigation";

import { Button, Space, Tag, Typography } from "antd";

const PAGE_META = {
  "/": {
    section: "需求采集",
    title: "专题提需工作台",
    description: "把一段模糊需求变成结构化槽位、参考资料、风险提示和 PRD。",
  },
  "/knowledge": {
    section: "知识运营",
    title: "知识库管理中心",
    description: "统一管理上传文档、版本、重建任务、召回测试和知识资产状态。",
  },
  "/graph": {
    section: "图谱分析",
    title: "GraphRAG 查询台",
    description: "基于已构建索引进行图谱查询、关系分析和社区报告阅读。",
  },
  "/manual": {
    section: "项目文档",
    title: "项目使用说明",
    description: "查看完整的企业级项目说明、操作手册、架构设计、启动方式与使用边界。",
  },
} as const;

const PAGE_ACTION = {
  "/": {
    label: "刷新系统状态",
    eventName: "ops:refresh:workbench",
  },
  "/knowledge": {
    label: "刷新知识状态",
    eventName: "ops:refresh:knowledge",
  },
  "/graph": {
    label: "刷新索引",
    eventName: "ops:refresh:graph",
  },
} as const;

export function SiteHeader() {
  const pathname = usePathname();
  const meta = PAGE_META[pathname as keyof typeof PAGE_META] ?? PAGE_META["/"];
  const action = PAGE_ACTION[pathname as keyof typeof PAGE_ACTION];

  return (
    <header className="admin-topbar">
      <div>
        <Typography.Text className="admin-breadcrumb">
          Topic Ops Console / {meta.section}
        </Typography.Text>
        <Typography.Title level={3} className="admin-topbar-title">
          {meta.title}
        </Typography.Title>
        <Typography.Paragraph className="admin-topbar-description">
          {meta.description}
        </Typography.Paragraph>
      </div>

      <div className="admin-topbar-actions">
        {action ? (
          <Button
            className="admin-topbar-refresh"
            onClick={() => window.dispatchEvent(new CustomEvent(action.eventName))}
          >
            {action.label}
          </Button>
        ) : null}

      </div>
    </header>
  );
}
