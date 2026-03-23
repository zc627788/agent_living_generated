"use client";

// 侧边栏负责提供后台管理系统式的全局导航，让页面职责一眼可见。

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Tag, Typography } from "antd";

const NAV_ITEMS = [
  {
    href: "/",
    title: "提需工作台",
    description: "会话采集、结构化结果、PRD 预览",
    badge: "Agent",
  },
  {
    href: "/knowledge",
    title: "知识库管理",
    description: "文档、版本、任务、召回测试",
    badge: "Ops",
  },
  {
    href: "/graph",
    title: "图谱查询",
    description: "GraphRAG 索引、关系图、社区报告",
    badge: "Graph",
  },
] as const;

export function AdminSidebar() {
  const pathname = usePathname();

  return (
    <aside className="admin-sidebar">
      <div className="admin-brand">
        <Typography.Title level={4} className="admin-brand-title">
          PRD Agent Studio
        </Typography.Title>
        <Typography.Paragraph className="admin-brand-description">
          面向产品、运营、设计和前端协作的专题需求后台。
        </Typography.Paragraph>
      </div>

      <nav className="admin-nav">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`admin-nav-item ${active ? "is-active" : ""}`}
            >
              <div className="admin-nav-head">
                <span className="admin-nav-title">{item.title}</span>
                <Tag color={active ? "blue" : "default"}>{item.badge}</Tag>
              </div>
              <span className="admin-nav-description">{item.description}</span>
            </Link>
          );
        })}
      </nav>

      <div className="admin-sidebar-footer">
        <Link
          href="/manual"
          className={`admin-doc-link ${pathname === "/manual" ? "is-active" : ""}`}
        >
          <div className="admin-nav-head">
            <span className="admin-nav-title">项目使用说明</span>
            <Tag color={pathname === "/manual" ? "blue" : "default"}>Doc</Tag>
          </div>
          <span className="admin-nav-description">
            打开完整项目手册，查看操作说明、架构意义、启动方式、知识库与 GraphRAG 使用规则。
          </span>
        </Link>
      </div>
    </aside>
  );
}
