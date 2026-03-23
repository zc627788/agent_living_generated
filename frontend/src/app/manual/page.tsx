import { readFile } from "node:fs/promises";
import path from "node:path";

import ManualViewer from "./components/manual-viewer";

async function loadProjectManual(filename: string) {
  const manualPath = path.join(process.cwd(), "..", "docs", filename);
  try {
    return await readFile(manualPath, "utf-8");
  } catch {
    return `# 手册读取失败\n\n未找到 \`docs/${filename}\`，请确认文件路径是否正确。`;
  }
}

export default async function ManualPage() {
  const markdown = await loadProjectManual("PROJECT_MANUAL.md");

  return (
    <div className="page-stack console-page">
      <ManualViewer markdown={markdown} />
    </div>
  );
}
