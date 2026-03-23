// AppShell 负责搭起整个后台管理系统的外壳，包括侧边导航、顶部栏和内容区。

import type { ReactNode } from "react";

import { AntdRegistry } from "@ant-design/nextjs-registry";
import { App, ConfigProvider } from "antd";

import { AdminSidebar } from "@/components/admin-sidebar";
import { SiteHeader } from "@/components/site-header";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  return (
    <AntdRegistry>
      <ConfigProvider
        theme={{
          token: {
            colorPrimary: "#2563eb",
            colorInfo: "#2563eb",
            colorSuccess: "#059669",
            colorWarning: "#d97706",
            colorError: "#dc2626",
            colorBgBase: "#f3f6fb",
            colorTextBase: "#0f172a",
            borderRadius: 14,
            fontFamily: "var(--font-body)",
            boxShadowSecondary: "0 18px 40px rgba(15, 23, 42, 0.08)",
          },
          components: {
            Card: {
              borderRadiusLG: 18,
            },
            Table: {
              headerBg: "#f8fafc",
              rowHoverBg: "#eff6ff",
            },
            Tabs: {
              itemSelectedColor: "#2563eb",
              itemActiveColor: "#1d4ed8",
            },
          },
        }}
      >
        <App>
          <div className="admin-shell">
            <AdminSidebar />
            <div className="admin-main">
              <SiteHeader />
              <main className="admin-content">{children}</main>
            </div>
          </div>
        </App>
      </ConfigProvider>
    </AntdRegistry>
  );
}
