// 首页直接承载提需工作台，避免多余的页面跳转层。

import { Workbench } from "@/components/workbench";

export default function Home() {
  return <Workbench />;
}
