"""PRD 草稿生成器。

这里先走确定性模板生成，优先保证结构完整和事实稳定，再交给 LLM 做润色与复核。
"""

from __future__ import annotations

from app.models.schemas import ReferenceCard


DEFAULT_MODULES = {
    "activity": ["KV 头图", "活动介绍", "奖池展示", "抽奖入口", "规则说明", "FAQ"],
    "display": ["KV 头图", "版本亮点", "核心卖点", "视觉展示", "CTA 引导", "FAQ"],
    "recruitment": ["KV 头图", "团队介绍", "岗位列表", "投递流程", "福利说明", "FAQ"],
}


def build_prd(
    title: str,
    topic_type: str,
    slots: dict[str, str],
    references: list[ReferenceCard],
    risk_alerts: list[str],
) -> str:
    modules = [item.strip() for item in slots.get("页面模块", "").split("、") if item.strip()]
    if not modules:
        modules = DEFAULT_MODULES.get(topic_type, DEFAULT_MODULES["display"])

    mermaid_nodes = []
    mermaid_links = []
    for index, module in enumerate(modules):
        node_id = f"M{index + 1}"
        mermaid_nodes.append(f'    {node_id}["{module}"]')
        if index > 0:
            mermaid_links.append(f"    M{index} --> {node_id}")

    references_md = "\n".join(
        (
            f"- ![缩略图]({reference.thumbnail_url})\n  [{reference.title}]({reference.url}) | {reference.section_path} | 相关度 `{reference.score}`"
            if reference.thumbnail_url and reference.url
            else f"- [{reference.title}]({reference.url}) | {reference.section_path} | 相关度 `{reference.score}`"
            if reference.url
            else f"- {reference.title} | {reference.section_path} | 相关度 `{reference.score}`"
        )
        for reference in references
    ) or "- 暂无外部参考，建议补充视觉偏好、竞品链接或上传带缩略图的知识条目。"

    risk_md = "\n".join(f"- {risk}" for risk in risk_alerts) or "- 当前未检测到高优先级风险。"

    tracking_name = {
        "activity": "点击_立即抽奖",
        "display": "点击_立即查看",
        "recruitment": "点击_立即投递",
    }.get(topic_type, "点击_主要按钮")

    return f"""# {title}

## 1. 基本信息
- 专题类型：{topic_type}
- 活动名称：{slots.get("活动名称", title)}
- 活动时间：{slots.get("活动时间", "待补充")}
- URL 后缀：{slots.get("URL后缀", "待补充")}
- 目标用户：{slots.get("目标用户", "待补充")}
- 风格关键词：{slots.get("风格关键词", "待补充")}

## 2. 页面结构图
```mermaid
flowchart TD
{chr(10).join(mermaid_nodes)}
{chr(10).join(mermaid_links)}
```

## 3. 页面模块说明
{chr(10).join(f"- {module}" for module in modules)}

## 4. 文案清单
- 主标题：{slots.get("主标题", slots.get("活动名称", title))}
- 副标题：{slots.get("副标题", "突出核心利益点与参与方式。")}
- 按钮文案：{slots.get("按钮文案", "立即参与")}
- 说明文案：{slots.get("说明文案", "请补充活动规则、资格限制与奖品说明。")}

## 5. 交互逻辑
- 用户进入专题页后默认聚焦 `KV 头图` 与主 CTA。
- 点击 `{slots.get("按钮文案", "立即参与")}` 后：
  - 若是活动类，进入抽奖弹窗或报名表单。
  - 若是展示类，跳转详情模块或下载入口。
  - 若是招聘类，跳转岗位筛选与投递区域。
- 表单提交或抽奖完成后，需要展示成功反馈与后续引导。

## 6. 数据埋点需求
- 页面曝光：`page_view_{topic_type}`
- 主按钮点击：`{tracking_name}`
- 模块曝光：`exposure_{modules[0]}`
- 结果反馈：`submit_success` / `submit_failed`

## 7. 参考图与案例
{references_md}

## 8. 风险提醒
{risk_md}
"""
