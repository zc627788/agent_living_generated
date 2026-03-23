// 根布局负责挂载全局字体、主题容器和站点级导航。

import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";

import "./globals.css";

export const metadata: Metadata = {
  title: "网站专题智能提需助手",
  description: "基于 Next.js、Ant Design、ahooks 与 FastAPI 的提需助手 MVP",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
