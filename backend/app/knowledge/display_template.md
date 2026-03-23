Title: 品牌展示专题模板
SourceType: template
Source: 内部展示模板库
URL: https://example.com/reference/brand-showcase
ThumbnailURL: https://placehold.co/640x360/png?text=%E5%B1%95%E7%A4%BA%E4%B8%93%E9%A2%98
Tags: display, branding, showcase

# 页面目标
展示类专题页的核心不是转盘式互动，而是清晰表达卖点、品牌心智和资产内容。页面结构要围绕“品牌主张 -> 产品亮点 -> 内容证明 -> 行动引导”展开。

# 标准结构
## 品牌主张
首屏需要一句话说明品牌主张，并配合视觉主 KV 与背景信息。

## 核心卖点
卖点区建议控制在 3 到 5 个模块内，每个模块都要有标题、解释文案和配图。

## 内容证明
可以使用数据、媒体报道、客户案例或功能演示作为证明，避免页面只有主观描述。

## 行动引导
展示类页面仍然需要预约、咨询、下载或跳转等明确 CTA，否则很难闭环。

# 交付清单
- 品牌主张文案
- 卖点结构
- 配图或视频资源
- CTA 设计
- 埋点建议

# 常见风险
如果只有视觉没有证据，页面会像纯海报。CTA 缺失时，专题页很难形成业务价值。






 对话编排流程 (LangGraph)                                                                                     │
     │                                                                                                              │
     │ user input → router → extractor → researcher → guardrails → planner                                          │
     │                                                         │                                                    │
     │                     ┌───────────────────────────────────┘                                                    │
     │                     │                                                                                        │
     │          ┌──────────┴──────────┐                                                                             │
     │          │                     │                                                                             │
     │     need_follow_up         !need_follow_up                                                                   │
     │          │                     │                                                                             │
     │          v                     v                                                                             │
     │   interviewer            builder → reviewer → output                                                         │
     │                                                                                                              │
     │ 节点职责:                                                                                                    │
     │ - router: 语义路由，判断专题类型 (activity/display/recruitment)                                              │
     │ - extractor: 槽位抽取，提取结构化信息                                                                        │
     │ - researcher: 知识检索，混合检索 (向量 + 关键词)                                                             │
     │ - guardrails: 风险检查，识别缺失/矛盾信息                                                                    │
     │ - planner: 对话规划，决定追问还是输出                                                                        │
     │ - interviewer: 生成澄清问题                                                                                  │
     │ - builder: 生成 PRD 草稿                                                                                     │
     │ - reviewer: PRD 复核与修订                    