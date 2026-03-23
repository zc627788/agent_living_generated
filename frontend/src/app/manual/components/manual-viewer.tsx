"use client";

import { Card, Tag } from "antd";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ManualViewerProps {
  markdown: string;
}

export default function ManualViewer({ markdown }: ManualViewerProps) {
  return (
    <>
      <div className="page-toolbar">
        <div className="inline-notice tone-info">
          <h5 className="inline-notice-title">项目完整操作手册</h5>
          <p className="inline-notice-description">
            本页面只展示当前代码版本对应的最新版文档，包含启动、页面功能、实操流程、输入输出边界和常见问题排查。
          </p>

        </div>
      </div>

      <Card className="panel-card panel-fill" variant="outlined">
        <div className="markdown-preview markdown-preview-fill">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
        </div>
      </Card>
    </>
  );
}
