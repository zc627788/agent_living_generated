"use client";

import type { ReactNode } from "react";

import { Space, Typography } from "antd";

type InlineNoticeProps = {
  title: string;
  description: ReactNode;
  tone?: "info" | "success" | "warning" | "error";
  extra?: ReactNode;
};

export function InlineNotice({
  title,
  description,
  tone = "info",
  extra,
}: InlineNoticeProps) {
  return (
    <div className={`inline-notice tone-${tone}`}>
      <div>
        <Typography.Title level={5} className="inline-notice-title">
          {title}
        </Typography.Title>
        <Typography.Paragraph className="inline-notice-description">
          {description}
        </Typography.Paragraph>
      </div>
      {extra ? <Space wrap>{extra}</Space> : null}
    </div>
  );
}
