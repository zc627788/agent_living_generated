"""LangGraph 对话编排服务。

这里是系统主脑，负责把模糊需求转成“可追问、可检索、可交付”的状态化工作流。
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.models.schemas import ReferenceCard, RetrievalOptions
from app.services.llm_service import llm_service
from app.services.prd import build_prd
from app.services.retriever import retriever

TOPIC_QUESTIONS = {
    "activity": {
        "活动时间": "活动具体开始和结束时间是什么？",
        "参与门槛": "用户参与活动前需要满足什么门槛，例如登录、预约或完成任务？",
        "奖品列表": "奖品有哪些，是否区分大奖、普通奖和保底奖励？",
        "核心玩法": "用户是抽奖、签到还是做任务领取奖励？每天可参与几次？",
        "风格关键词": "页面视觉更偏哪种风格，例如国风、赛博朋克、热血？",
        "URL后缀": "预计专题页 URL 后缀是什么？",
    },
    "display": {
        "活动时间": "这个专题的上线时间和下线时间是什么？",
        "核心卖点": "这次版本或内容最想突出哪 3 个卖点？",
        "目标用户": "这个专题主要面向新用户、回流用户还是核心玩家？",
        "风格关键词": "页面希望偏什么风格？",
        "URL后缀": "预计专题页 URL 后缀是什么？",
    },
    "recruitment": {
        "活动时间": "招聘活动的投递开放和截止时间是什么？",
        "岗位列表": "这次主要招哪些岗位，是否需要区分校招和社招？",
        "投递方式": "用户点击后是跳转招聘官网还是弹窗投递？",
        "目标用户": "面向什么人群，例如应届生、资深研发或设计师？",
        "风格关键词": "页面希望传达什么样的雇主品牌氛围？",
    },
}

TOPIC_REQUIRED_SLOTS = {
    "activity": ["活动名称", "活动时间", "参与门槛", "奖品列表", "核心玩法", "风格关键词", "URL后缀"],
    "display": ["活动名称", "活动时间", "核心卖点", "目标用户", "风格关键词", "URL后缀"],
    "recruitment": ["活动名称", "活动时间", "岗位列表", "投递方式", "目标用户", "风格关键词"],
}

DEFAULT_SLOT_VALUES = {
    "activity": {
        "页面模块": "KV 头图、活动介绍、奖池展示、抽奖入口、规则说明、FAQ",
        "按钮文案": "立即抽奖",
        "主标题": "节日限定活动",
        "副标题": "参与互动即可领取限定奖励",
    },
    "display": {
        "页面模块": "KV 头图、版本亮点、核心卖点、角色展示、CTA 引导、FAQ",
        "按钮文案": "立即查看",
        "主标题": "版本专题上线",
        "副标题": "快速理解本次更新内容与体验亮点",
    },
    "recruitment": {
        "页面模块": "KV 头图、团队介绍、岗位列表、投递流程、福利说明、FAQ",
        "按钮文案": "立即投递",
        "主标题": "加入我们",
        "副标题": "与你一起打造更好的产品与体验",
    },
}

NODE_STATUS = {
    "router": "语义路由完成",
    "extractor": "槽位抽取完成",
    "researcher": "知识检索完成",
    "guardrails": "风险护栏检查完成",
    "planner": "对话规划完成",
    "interviewer": "生成澄清追问",
    "builder": "生成 PRD 草稿",
    "reviewer": "完成文档复核",
}

NODE_DETAIL = {
    "router": "先做语义路由，判断需求属于哪一类专题。",
    "extractor": "抽取并合并标题、时间、玩法、岗位和 CTA 等结构化槽位。",
    "researcher": "去知识库检索模板、规范和案例，补充业务依据。",
    "guardrails": "检查时间、奖品、岗位、链接等明显风险，避免直接产出错误 PRD。",
    "planner": "判断当前信息是否足够交付，还是应该继续提问。",
    "interviewer": "整理成下一轮追问，只追问最关键的缺失信息。",
    "builder": "根据当前槽位和知识命中生成 PRD 草稿。",
    "reviewer": "对草稿做复核，减少遗漏、冲突和幻觉。",
}


class InterviewState(TypedDict, total=False):
    latest_message: str
    history: list[str]
    current_slots: dict[str, str]
    current_topic_type: str | None
    retrieval: RetrievalOptions
    topic_type: str
    topic_reason: str
    title: str
    slots: dict[str, str]
    missing_slots: list[str]
    risk_alerts: list[str]
    references: list[ReferenceCard]
    rewritten_query: str
    need_follow_up: bool
    assistant_fallback: str
    assistant_mode: Literal["follow_up", "delivery"]
    prd_markdown: str
    review_issues: list[str]


@dataclass
class InterviewResult:
    title: str
    topic_type: str
    slots: dict[str, str]
    missing_slots: list[str]
    risk_alerts: list[str]
    references: list[ReferenceCard]
    assistant_message: str
    prd_markdown: str


class InterviewService:
    def __init__(self) -> None:
        # 状态图明确区分路由、抽取、检索、护栏、规划、追问、构建、复核几个阶段，
        # 比线性 pipeline 更容易继续演进成多 Agent 协作。
        graph = StateGraph(InterviewState)
        graph.add_node("router", self._route_node)
        graph.add_node("extractor", self._extractor_node)
        graph.add_node("researcher", self._researcher_node)
        graph.add_node("guardrails", self._guardrails_node)
        graph.add_node("planner", self._planner_node)
        graph.add_node("interviewer", self._interviewer_node)
        graph.add_node("builder", self._builder_node)
        graph.add_node("reviewer", self._reviewer_node)
        graph.add_edge(START, "router")
        graph.add_edge("router", "extractor")
        graph.add_edge("extractor", "researcher")
        graph.add_edge("researcher", "guardrails")
        graph.add_edge("guardrails", "planner")
        graph.add_conditional_edges(
            "planner",
            self._choose_next_node,
            {
                "interviewer": "interviewer",
                "builder": "builder",
            },
        )
        graph.add_edge("interviewer", END)
        graph.add_edge("builder", "reviewer")
        graph.add_edge("reviewer", END)
        self.workflow = graph.compile()

    def run(
        self,
        latest_message: str,
        history: list[str],
        current_slots: dict[str, str],
        current_topic_type: str | None,
        retrieval: RetrievalOptions | None = None,
    ) -> InterviewResult:
        """同步执行一次完整对话流程，适合普通 JSON 接口。"""
        state = self.workflow.invoke(
            {
                "latest_message": latest_message,
                "history": history,
                "current_slots": current_slots,
                "current_topic_type": current_topic_type,
                "retrieval": retrieval or RetrievalOptions(),
            }
        )
        assistant_message = self._generate_assistant_message(state)
        return self._to_result(state, assistant_message)

    def stream(
        self,
        latest_message: str,
        history: list[str],
        current_slots: dict[str, str],
        current_topic_type: str | None,
        retrieval: RetrievalOptions | None = None,
    ) -> Iterable[dict]:
        """以事件流方式返回节点状态、节点输入输出和最终结果。"""
        initial_state: InterviewState = {
            "latest_message": latest_message,
            "history": history,
            "current_slots": current_slots,
            "current_topic_type": current_topic_type,
            "retrieval": retrieval or RetrievalOptions(),
        }
        state = dict(initial_state)
        node_sequence = [
            ("router", self._route_node),
            ("extractor", self._extractor_node),
            ("researcher", self._researcher_node),
            ("guardrails", self._guardrails_node),
            ("planner", self._planner_node),
        ]

        for node_name, handler in node_sequence:
            yield from self._execute_stream_node(node_name, handler, state)

        if self._choose_next_node(state) == "interviewer":
            yield from self._execute_stream_node("interviewer", self._interviewer_node, state)
        else:
            yield from self._execute_stream_node("builder", self._builder_node, state)
            yield from self._execute_stream_node("reviewer", self._reviewer_node, state)

        chunks: list[str] = []
        for chunk in self._stream_assistant_message(state):
            chunks.append(chunk)
            yield {"event": "delta", "data": {"content": chunk}}

        assistant_message = "".join(chunks).strip() or state.get("assistant_fallback", "")
        yield {"event": "result", "data": self._to_result(state, assistant_message)}

    def _execute_stream_node(
        self,
        node_name: str,
        handler: Any,
        state: dict[str, Any],
    ) -> Iterable[dict]:
        trace_id = uuid.uuid4().hex
        started_at = self._now_iso()
        input_snapshot = self._build_trace_input(node_name, state)
        yield {
            "event": "status",
            "data": {
                "trace_id": trace_id,
                "node": node_name,
                "message": NODE_STATUS.get(node_name, node_name),
                "detail": NODE_DETAIL.get(node_name, ""),
                "phase": "started",
                "status": "running",
                "created_at": started_at,
                "started_at": started_at,
                "input": input_snapshot,
            },
        }

        try:
            payload = handler(state)
            state.update(payload)
            finished_at = self._now_iso()
            yield {
                "event": "status",
                "data": {
                    "trace_id": trace_id,
                    "node": node_name,
                    "message": NODE_STATUS.get(node_name, node_name),
                    "detail": NODE_DETAIL.get(node_name, ""),
                    "phase": "completed",
                    "status": "succeeded",
                    "created_at": finished_at,
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "input": input_snapshot,
                    "output": self._build_trace_output(node_name, payload, state),
                },
            }
        except Exception as error:
            failed_at = self._now_iso()
            yield {
                "event": "status",
                "data": {
                    "trace_id": trace_id,
                    "node": node_name,
                    "message": NODE_STATUS.get(node_name, node_name),
                    "detail": NODE_DETAIL.get(node_name, ""),
                    "phase": "failed",
                    "status": "failed",
                    "created_at": failed_at,
                    "started_at": started_at,
                    "finished_at": failed_at,
                    "input": input_snapshot,
                    "error": str(error),
                },
            }
            raise

    def _build_trace_input(self, node_name: str, state: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "latest_message": state.get("latest_message", ""),
            "history_count": len(state.get("history", [])),
            "current_topic_type": state.get("current_topic_type"),
            "retrieval": self._serialize_retrieval(state.get("retrieval")),
        }
        if node_name in {"extractor", "researcher", "guardrails", "planner", "interviewer", "builder", "reviewer"}:
            payload["topic_type"] = state.get("topic_type")
            payload["title"] = state.get("title")
            payload["slots"] = self._clip_slots(state.get("slots", {}))
        if node_name in {"researcher", "guardrails", "planner", "interviewer", "builder", "reviewer"}:
            payload["references"] = self._summarize_references(state.get("references", []))
        if node_name in {"planner", "interviewer", "builder", "reviewer"}:
            payload["risk_alerts"] = state.get("risk_alerts", [])[:6]
        if node_name in {"interviewer", "builder", "reviewer"}:
            payload["missing_slots"] = state.get("missing_slots", [])[:8]
        if node_name == "reviewer":
            payload["prd_preview"] = self._clip_text(state.get("prd_markdown", ""), 600)
        return payload

    def _build_trace_output(
        self,
        node_name: str,
        payload: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        if node_name == "router":
            return {
                "topic_type": payload.get("topic_type"),
                "topic_reason": self._clip_text(str(payload.get("topic_reason", "")), 200),
            }
        if node_name == "extractor":
            return {
                "title": payload.get("title"),
                "slots": self._clip_slots(payload.get("slots", {})),
            }
        if node_name == "researcher":
            return {
                "query": self._clip_text(self._build_research_query(state), 280),
                "rewritten_query": payload.get("rewritten_query"),
                "references": self._summarize_references(payload.get("references", [])),
            }
        if node_name == "guardrails":
            return {"risk_alerts": payload.get("risk_alerts", [])[:8]}
        if node_name == "planner":
            return {
                "missing_slots": payload.get("missing_slots", [])[:8],
                "need_follow_up": payload.get("need_follow_up", False),
            }
        if node_name in {"interviewer", "builder"}:
            return {
                "assistant_mode": payload.get("assistant_mode"),
                "prd_preview": self._clip_text(str(payload.get("prd_markdown", "")), 600),
            }
        if node_name == "reviewer":
            return {
                "review_issues": payload.get("review_issues", [])[:8],
                "risk_alerts": payload.get("risk_alerts", [])[:8],
                "prd_preview": self._clip_text(str(payload.get("prd_markdown", "")), 600),
            }
        return {
            key: value for key, value in payload.items() if value is not None
        }

    def _build_research_query(self, state: dict[str, Any]) -> str:
        return " ".join(
            filter(
                None,
                [
                    str(state.get("latest_message", "")),
                    str(state.get("title", "")),
                    str(state.get("slots", {}).get("核心卖点", "")),
                    str(state.get("slots", {}).get("奖品列表", "")),
                    str(state.get("slots", {}).get("岗位列表", "")),
                ],
            )
        )

    def _serialize_retrieval(self, retrieval: Any) -> dict[str, Any] | None:
        if retrieval is None:
            return None
        if isinstance(retrieval, RetrievalOptions):
            return retrieval.model_dump(mode="json")
        return dict(retrieval)

    def _summarize_references(self, references: list[ReferenceCard]) -> list[dict[str, Any]]:
        return [
            {
                "title": reference.title,
                "source": reference.source,
                "score": reference.score,
                "section_path": reference.section_path,
            }
            for reference in references[:5]
        ]

    def _clip_slots(self, slots: dict[str, str]) -> dict[str, str]:
        return {
            key: self._clip_text(value, 120)
            for key, value in list(slots.items())[:12]
        }

    def _clip_text(self, value: str, limit: int) -> str:
        text = value.strip()
        if len(text) <= limit:
            return text
        return f"{text[:limit]}..."

    def _now_iso(self) -> str:
        return datetime.now().isoformat()

    def _route_node(self, state: InterviewState) -> InterviewState:
        route = llm_service.route_topic(state["latest_message"], state["history"])
        topic_type = state.get("current_topic_type") or route.topic_type
        return {
            "topic_type": topic_type,
            "topic_reason": route.reason,
        }

    def _extractor_node(self, state: InterviewState) -> InterviewState:
        topic_type = state["topic_type"]
        current_slots = dict(DEFAULT_SLOT_VALUES.get(topic_type, {}))
        current_slots.update(state.get("current_slots", {}))
        allowed_slots = TOPIC_REQUIRED_SLOTS[topic_type] + ["页面模块", "按钮文案", "主标题", "副标题"]
        llm_result = llm_service.extract_slots(
            latest_message=state["latest_message"],
            history=state["history"],
            topic_type=topic_type,
            current_slots=current_slots,
            allowed_slots=allowed_slots,
        )

        extracted = dict(current_slots)
        extracted.update(self._extract_slots_with_regex(state["latest_message"]))
        extracted.update({key: value for key, value in llm_result.slots.items() if key in allowed_slots and value})

        title = extracted.get("活动名称") or llm_result.title or self._guess_title(state["latest_message"], topic_type)
        extracted["活动名称"] = title
        return {
            "title": title,
            "slots": extracted,
        }

    def _researcher_node(self, state: InterviewState) -> InterviewState:
        query = " ".join(
            filter(
                None,
                [
                    state["latest_message"],
                    state.get("title", ""),
                    state["slots"].get("核心卖点", ""),
                    state["slots"].get("奖品列表", ""),
                    state["slots"].get("岗位列表", ""),
                ],
            )
        )
        rewritten_query, references = retriever.search_with_diagnostics(
            query=query,
            topic_type=state["topic_type"],
            retrieval=state["retrieval"],
        )
        return {
            "rewritten_query": rewritten_query,
            "references": references,
        }

    def _guardrails_node(self, state: InterviewState) -> InterviewState:
        llm_risks = llm_service.analyze_risks(
            topic_type=state["topic_type"],
            latest_message=state["latest_message"],
            slots=state["slots"],
            references=state.get("references", []),
        )
        merged_risks = []
        for risk in self._detect_risks(state["slots"], state["topic_type"]) + llm_risks.risks:
            if risk and risk not in merged_risks:
                merged_risks.append(risk)
        return {"risk_alerts": merged_risks}

    def _planner_node(self, state: InterviewState) -> InterviewState:
        topic_type = state["topic_type"]
        missing_slots = [slot for slot in TOPIC_REQUIRED_SLOTS[topic_type] if not state["slots"].get(slot)]
        return {
            "missing_slots": missing_slots,
            "need_follow_up": bool(missing_slots),
        }

    def _interviewer_node(self, state: InterviewState) -> InterviewState:
        fallback_message = self._build_follow_up_fallback(
            topic_type=state["topic_type"],
            slots=state["slots"],
            missing_slots=state["missing_slots"],
            risk_alerts=state["risk_alerts"],
        )
        prd_markdown = build_prd(
            title=state["title"],
            topic_type=state["topic_type"],
            slots=state["slots"],
            references=state.get("references", []),
            risk_alerts=state["risk_alerts"],
        )
        return {
            "assistant_mode": "follow_up",
            "assistant_fallback": fallback_message,
            "prd_markdown": prd_markdown,
        }

    def _builder_node(self, state: InterviewState) -> InterviewState:
        fallback_prd = build_prd(
            title=state["title"],
            topic_type=state["topic_type"],
            slots=state["slots"],
            references=state.get("references", []),
            risk_alerts=state["risk_alerts"],
        )
        prd_markdown = llm_service.generate_prd(
            topic_type=state["topic_type"],
            slots=state["slots"],
            risk_alerts=state["risk_alerts"],
            references=state.get("references", []),
            fallback=fallback_prd,
        )
        return {
            "assistant_mode": "delivery",
            "assistant_fallback": self._build_delivery_fallback(state["topic_type"], state["slots"], state["risk_alerts"]),
            "prd_markdown": prd_markdown,
        }

    def _reviewer_node(self, state: InterviewState) -> InterviewState:
        review = llm_service.review_prd(
            topic_type=state["topic_type"],
            slots=state["slots"],
            risk_alerts=state["risk_alerts"],
            prd_markdown=state["prd_markdown"],
        )
        prd_markdown = state["prd_markdown"]
        if review.revised_prd.strip():
            prd_markdown = review.revised_prd.strip()
        return {
            "prd_markdown": prd_markdown,
            "review_issues": review.issues,
            "risk_alerts": self._merge_lists(state["risk_alerts"], review.issues),
        }

    def _choose_next_node(self, state: InterviewState) -> Literal["interviewer", "builder"]:
        return "interviewer" if state["need_follow_up"] else "builder"

    def _generate_assistant_message(self, state: InterviewState) -> str:
        if state["assistant_mode"] == "follow_up":
            return llm_service.generate_follow_up(
                topic_type=state["topic_type"],
                conversation=state["history"] + [state["latest_message"]],
                slots=state["slots"],
                missing_slots=state["missing_slots"],
                risk_alerts=state["risk_alerts"],
                references=state.get("references", []),
                fallback=state["assistant_fallback"],
            )
        return llm_service.generate_delivery_message(
            topic_type=state["topic_type"],
            slots=state["slots"],
            risk_alerts=state["risk_alerts"],
            references=state.get("references", []),
            fallback=state["assistant_fallback"],
        )

    def _stream_assistant_message(self, state: InterviewState) -> Iterable[str]:
        if state["assistant_mode"] == "follow_up":
            yield from llm_service.stream_follow_up(
                topic_type=state["topic_type"],
                conversation=state["history"] + [state["latest_message"]],
                slots=state["slots"],
                missing_slots=state["missing_slots"],
                risk_alerts=state["risk_alerts"],
                references=state.get("references", []),
                fallback=state["assistant_fallback"],
            )
            return
        yield from llm_service.stream_delivery_message(
            topic_type=state["topic_type"],
            slots=state["slots"],
            risk_alerts=state["risk_alerts"],
            references=state.get("references", []),
            fallback=state["assistant_fallback"],
        )

    def _to_result(self, state: InterviewState, assistant_message: str) -> InterviewResult:
        return InterviewResult(
            title=state["title"],
            topic_type=state["topic_type"],
            slots=state["slots"],
            missing_slots=state["missing_slots"],
            risk_alerts=state["risk_alerts"],
            references=state.get("references", []),
            assistant_message=assistant_message,
            prd_markdown=state["prd_markdown"],
        )

    def _build_follow_up_fallback(
        self,
        *,
        topic_type: str,
        slots: dict[str, str],
        missing_slots: list[str],
        risk_alerts: list[str],
    ) -> str:
        filled_summary = "；".join(
            f"{key}: {value}"
            for key, value in slots.items()
            if key
            in {
                "活动名称",
                "活动时间",
                "参与门槛",
                "奖品列表",
                "核心玩法",
                "风格关键词",
                "URL后缀",
                "核心卖点",
                "岗位列表",
                "投递方式",
            }
            and value
        )
        questions = [TOPIC_QUESTIONS[topic_type][slot] for slot in missing_slots[:3]]
        if questions:
            message = (
                f"已识别为 `{topic_type}` 类专题。当前已确认：{filled_summary or '暂未形成可用结构化信息'}。\n\n"
                f"为了继续完善 PRD，请先补充这 {len(questions)} 项：\n"
                + "\n".join(f"{index + 1}. {question}" for index, question in enumerate(questions))
            )
        else:
            message = "核心信息已经基本完整，我先整理出一版可交付 PRD，后续再补参考图和最终文案。"
        if risk_alerts:
            message += "\n\n另外有几项风险需要你确认：\n" + "\n".join(f"- {risk}" for risk in risk_alerts[:4])
        return message

    def _build_delivery_fallback(
        self,
        topic_type: str,
        slots: dict[str, str],
        risk_alerts: list[str],
    ) -> str:
        message = (
            f"我已经基于当前信息整理出一版 `{topic_type}` 专题 PRD。"
            f"页面核心会围绕“{slots.get('活动名称', '专题项目')}”展开，"
            "右侧预览可以直接用于评审。"
        )
        if risk_alerts:
            message += "\n\n同时保留了这些待确认风险：\n" + "\n".join(f"- {item}" for item in risk_alerts[:4])
        return message

    def _extract_slots_with_regex(self, text: str) -> dict[str, str]:
        slots: dict[str, str] = {}
        normalized = text.replace("\n", " ")

        date_range = re.search(
            r"((?:20\d{2}[年/-]\d{1,2}[月/-]\d{1,2}日?)\s*(?:至|到|-|~)\s*(?:20\d{2}[年/-]\d{1,2}[月/-]\d{1,2}日?)|(?:\d{1,2}月\d{1,2}日?\s*(?:至|到|-|~)\s*(?:\d{1,2}月\d{1,2}日?)))",
            normalized,
        )
        if date_range:
            slots["活动时间"] = date_range.group(1)

        suffix = self._capture_after(normalized, ["URL后缀", "url后缀", "后缀", "链接"])
        if suffix:
            slots["URL后缀"] = suffix.strip("/")

        style = self._capture_after(
            normalized,
            ["风格偏", "风格要", "风格走", "风格希望", "风格", "色调偏", "视觉偏"],
        )
        if style:
            slots["风格关键词"] = style

        audience = self._capture_after(normalized, ["目标用户", "主要用户", "面向"])
        if audience:
            slots["目标用户"] = audience

        chance = re.search(r"每天.*?(\d+)\s*次", normalized)
        if chance:
            slots["核心玩法"] = f"用户每天可参与 {chance.group(1)} 次"

        prize = self._capture_after(normalized, ["奖品包括", "奖品有", "奖品是", "奖池包括", "奖池有"])
        if prize:
            slots["奖品列表"] = prize

        threshold = self._capture_after(normalized, ["门槛是", "门槛为", "参与条件是", "参与条件为", "资格是"])
        if threshold:
            slots["参与门槛"] = threshold

        sell_points = self._capture_after(normalized, ["卖点是", "卖点有", "亮点是", "亮点有"])
        if sell_points:
            slots["核心卖点"] = sell_points

        positions = self._capture_after(normalized, ["招聘岗位有", "岗位有", "岗位包括"])
        if positions:
            slots["岗位列表"] = positions

        delivery = self._capture_after(normalized, ["投递方式是", "投递方式为", "投递是", "报名方式是"])
        if delivery:
            slots["投递方式"] = delivery

        explicit_name = self._capture_name(normalized)
        if explicit_name:
            slots["活动名称"] = explicit_name

        return slots

    def _capture_after(self, text: str, markers: list[str]) -> str:
        for marker in markers:
            if marker not in text:
                continue
            fragment = text.split(marker, 1)[1].strip("：: ")
            value = re.split(r"[，。；\n]", fragment, maxsplit=1)[0].strip()
            if value:
                return value
        return ""

    def _capture_name(self, text: str) -> str:
        for marker in ["做一个", "做个", "想做", "需要一个", "要做"]:
            if marker not in text:
                continue
            fragment = text.split(marker, 1)[1]
            for ending in ["专题页", "活动页", "页面", "官网"]:
                if ending in fragment:
                    name = fragment.split(ending, 1)[0].strip("，。； ")
                    return name.removesuffix("的").strip()
        return ""

    def _guess_title(self, text: str, topic_type: str) -> str:
        candidate = re.sub(r"[，。；,.!？?]", " ", text).strip()
        if len(candidate) > 24:
            candidate = candidate[:24].strip()
        if candidate:
            return candidate
        fallback = {
            "activity": "未命名活动专题",
            "display": "未命名展示专题",
            "recruitment": "未命名招聘专题",
        }
        return fallback[topic_type]

    def _detect_risks(self, slots: dict[str, str], topic_type: str) -> list[str]:
        risks: list[str] = []
        activity_time = slots.get("活动时间", "")
        if not activity_time:
            risks.append("缺少活动时间，无法评估排期、曝光周期与下线策略。")
        elif not re.search(r"(至|到|-|~)", activity_time):
            risks.append("活动时间未体现开始和结束边界，建议补全完整时间范围。")

        if topic_type == "activity" and not slots.get("奖品列表"):
            risks.append("活动类专题未给出奖品列表，页面结构和 CTA 文案会缺乏锚点。")

        if topic_type == "recruitment" and not slots.get("岗位列表"):
            risks.append("招聘专题未说明岗位范围，无法输出有效的岗位信息架构。")

        if not slots.get("URL后缀") and topic_type != "recruitment":
            risks.append("未提供 URL 后缀，提测和发布环节仍需二次确认。")

        return risks

    def _merge_lists(self, left: list[str], right: list[str]) -> list[str]:
        merged = list(left)
        for item in right:
            if item and item not in merged:
                merged.append(item)
        return merged


interview_service = InterviewService()
