"""大模型能力封装层。

统一承接 Qwen 聊天、结构化 JSON 输出、Embedding、PRD Review 与图谱摘要等能力。
"""

from __future__ import annotations

import json
from typing import Iterable, Literal, TypeVar

import requests
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.core.config import settings
from app.models.schemas import ReferenceCard

T = TypeVar("T", bound=BaseModel)


class TopicRouteDecision(BaseModel):
    topic_type: Literal["activity", "display", "recruitment"] = "activity"
    reason: str = ""


class SlotExtractionResult(BaseModel):
    title: str = ""
    slots: dict[str, str] = Field(default_factory=dict)


class GuardrailResult(BaseModel):
    risks: list[str] = Field(default_factory=list)
    reasoning: str = ""


class QueryRewriteResult(BaseModel):
    query: str = ""


class PrdReviewResult(BaseModel):
    approved: bool = True
    issues: list[str] = Field(default_factory=list)
    revised_prd: str = ""


class LlmService:
    def __init__(self) -> None:
        self.chat_model = ChatOpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.qwen_base_url,
            model=settings.qwen_chat_model,
            temperature=0.2,
            streaming=True,
            max_retries=2,
            timeout=60,
        )

    def chat_ready(self) -> bool:
        return bool(settings.dashscope_api_key)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """调用 Qwen Embedding 接口，批量生成向量。"""
        vectors: list[list[float]] = []
        headers = {
            "Authorization": f"Bearer {settings.dashscope_api_key}",
            "Content-Type": "application/json",
        }
        normalized = [text.replace("\n", " ").strip()[:2000] for text in texts]
        for start in range(0, len(normalized), 8):
            batch = normalized[start : start + 8]
            response = requests.post(
                f"{settings.qwen_base_url}/embeddings",
                headers=headers,
                data=json.dumps(
                    {
                        "model": settings.qwen_embedding_model,
                        "input": batch,
                    },
                    ensure_ascii=False,
                ).encode("utf-8"),
                timeout=60,
            )
            if not response.ok:
                raise RuntimeError(f"DashScope embedding failed: {response.status_code} {response.text}")
            data = response.json().get("data", [])
            vectors.extend(item["embedding"] for item in data)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def route_topic(self, latest_message: str, history: list[str]) -> TopicRouteDecision:
        fallback = TopicRouteDecision(topic_type=self._fallback_route(latest_message), reason="fallback")
        if not self.chat_ready():
            return fallback

        return self._invoke_json(
            model=TopicRouteDecision,
            fallback=fallback,
            messages=[
                SystemMessage(
                    content=(
                        "你是专题需求路由器。"
                        "请根据用户输入在 activity、display、recruitment 中选择一个 topic_type。"
                        "只能返回 JSON。"
                    )
                ),
                HumanMessage(
                    content=json.dumps(
                        {
                            "latest_message": latest_message,
                            "history": history[-6:],
                        },
                        ensure_ascii=False,
                    )
                ),
            ],
        )

    def extract_slots(
        self,
        *,
        latest_message: str,
        history: list[str],
        topic_type: str,
        current_slots: dict[str, str],
        allowed_slots: list[str],
    ) -> SlotExtractionResult:
        fallback = SlotExtractionResult(title="", slots={})
        if not self.chat_ready():
            return fallback

        return self._invoke_json(
            model=SlotExtractionResult,
            fallback=fallback,
            messages=[
                SystemMessage(
                    content=(
                        "你是专题需求信息抽取器。"
                        "请从用户对话中抽取标题和结构化槽位。"
                        "只能填写提供的 allowed_slots，未提及则不要编造。"
                        "只返回 JSON。"
                    )
                ),
                HumanMessage(
                    content=json.dumps(
                        {
                            "topic_type": topic_type,
                            "allowed_slots": allowed_slots,
                            "current_slots": current_slots,
                            "history": history[-6:],
                            "latest_message": latest_message,
                        },
                        ensure_ascii=False,
                    )
                ),
            ],
        )

    def analyze_risks(
        self,
        *,
        topic_type: str,
        latest_message: str,
        slots: dict[str, str],
        references: list[ReferenceCard],
    ) -> GuardrailResult:
        fallback = GuardrailResult(risks=[], reasoning="fallback")
        if not self.chat_ready():
            return fallback

        return self._invoke_json(
            model=GuardrailResult,
            fallback=fallback,
            messages=[
                SystemMessage(
                    content=(
                        "你是企业专题需求的 AI Guardrails。"
                        "请检查时间、链接、资格、奖品、岗位、对外发布风险、信息缺失风险。"
                        "仅输出简洁的风险列表，不要重复同义项。只返回 JSON。"
                    )
                ),
                HumanMessage(
                    content=json.dumps(
                        {
                            "topic_type": topic_type,
                            "latest_message": latest_message,
                            "slots": slots,
                            "references": [
                                {
                                    "title": item.title,
                                    "source": item.source,
                                    "section_path": item.section_path,
                                    "score": item.score,
                                }
                                for item in references[:4]
                            ],
                        },
                        ensure_ascii=False,
                    )
                ),
            ],
        )

    def rewrite_query(self, query: str, topic_type: str) -> str:
        fallback = QueryRewriteResult(query=query.strip())
        if not self.chat_ready():
            return fallback.query

        result = self._invoke_json(
            model=QueryRewriteResult,
            fallback=fallback,
            messages=[
                SystemMessage(
                    content=(
                        "你是知识检索 Query Rewriter。"
                        "请将用户问题改写成适合专题知识库检索的中文短查询。"
                        "保留关键业务实体、活动类型、页面模块和限制条件。只返回 JSON。"
                    )
                ),
                HumanMessage(
                    content=json.dumps(
                        {
                            "topic_type": topic_type,
                            "query": query,
                        },
                        ensure_ascii=False,
                    )
                ),
            ],
        )
        return result.query.strip() or query.strip()

    def generate_follow_up(
        self,
        *,
        topic_type: str,
        conversation: list[str],
        slots: dict[str, str],
        missing_slots: list[str],
        risk_alerts: list[str],
        references: list[ReferenceCard],
        fallback: str,
    ) -> str:
        if not self.chat_ready():
            return fallback
        return self._invoke_text(
            self._build_follow_up_messages(
                topic_type=topic_type,
                conversation=conversation,
                slots=slots,
                missing_slots=missing_slots,
                risk_alerts=risk_alerts,
                references=references,
                fallback=fallback,
            ),
            fallback=fallback,
        )

    def stream_follow_up(
        self,
        *,
        topic_type: str,
        conversation: list[str],
        slots: dict[str, str],
        missing_slots: list[str],
        risk_alerts: list[str],
        references: list[ReferenceCard],
        fallback: str,
    ) -> Iterable[str]:
        if not self.chat_ready():
            yield fallback
            return
        yield from self._stream_text(
            self._build_follow_up_messages(
                topic_type=topic_type,
                conversation=conversation,
                slots=slots,
                missing_slots=missing_slots,
                risk_alerts=risk_alerts,
                references=references,
                fallback=fallback,
            ),
            fallback=fallback,
        )

    def generate_delivery_message(
        self,
        *,
        topic_type: str,
        slots: dict[str, str],
        risk_alerts: list[str],
        references: list[ReferenceCard],
        fallback: str,
    ) -> str:
        if not self.chat_ready():
            return fallback
        return self._invoke_text(
            [
                SystemMessage(
                    content=(
                        "你是资深专题 PM 助手。"
                        "请将已完成的 PRD 交付说明润色为简洁、专业、可执行的中文回复。"
                        "禁止虚构新事实。"
                    )
                ),
                HumanMessage(
                    content=json.dumps(
                        {
                            "topic_type": topic_type,
                            "slots": slots,
                            "risk_alerts": risk_alerts,
                            "references": [item.title for item in references[:4]],
                            "draft": fallback,
                        },
                        ensure_ascii=False,
                    )
                ),
            ],
            fallback=fallback,
        )

    def stream_delivery_message(
        self,
        *,
        topic_type: str,
        slots: dict[str, str],
        risk_alerts: list[str],
        references: list[ReferenceCard],
        fallback: str,
    ) -> Iterable[str]:
        if not self.chat_ready():
            yield fallback
            return
        yield from self._stream_text(
            [
                SystemMessage(
                    content=(
                        "你是资深专题 PM 助手。"
                        "请将已完成的 PRD 交付说明润色为简洁、专业、可执行的中文回复。"
                        "禁止虚构新事实。"
                    )
                ),
                HumanMessage(
                    content=json.dumps(
                        {
                            "topic_type": topic_type,
                            "slots": slots,
                            "risk_alerts": risk_alerts,
                            "references": [item.title for item in references[:4]],
                            "draft": fallback,
                        },
                        ensure_ascii=False,
                    )
                ),
            ],
            fallback=fallback,
        )

    def generate_prd(
        self,
        *,
        topic_type: str,
        slots: dict[str, str],
        risk_alerts: list[str],
        references: list[ReferenceCard],
        fallback: str,
    ) -> str:
        if not self.chat_ready():
            return fallback

        return self._invoke_text(
            [
                SystemMessage(
                    content=(
                        "你是网站专题 PRD 写作助手。"
                        "请润色一份已经确定事实的 Markdown PRD。"
                        "禁止编造新业务信息，禁止删除章节。"
                    )
                ),
                HumanMessage(
                    content=json.dumps(
                        {
                            "topic_type": topic_type,
                            "slots": slots,
                            "risk_alerts": risk_alerts,
                            "reference_titles": [item.title for item in references[:4]],
                            "draft": fallback,
                        },
                        ensure_ascii=False,
                    )
                ),
            ],
            fallback=fallback,
        )

    def review_prd(
        self,
        *,
        topic_type: str,
        slots: dict[str, str],
        risk_alerts: list[str],
        prd_markdown: str,
    ) -> PrdReviewResult:
        fallback = PrdReviewResult(approved=True, issues=[], revised_prd="")
        if not self.chat_ready():
            return fallback

        return self._invoke_json(
            model=PrdReviewResult,
            fallback=fallback,
            messages=[
                SystemMessage(
                    content=(
                        "你是专题 PRD Critic。"
                        "请检查文档是否遗漏核心结构、是否与已知槽位冲突、是否缺少风险说明。"
                        "如果需要修正，请在 revised_prd 中返回完整修正版，否则返回空字符串。只返回 JSON。"
                    )
                ),
                HumanMessage(
                    content=json.dumps(
                        {
                            "topic_type": topic_type,
                            "slots": slots,
                            "risk_alerts": risk_alerts,
                            "prd_markdown": prd_markdown,
                        },
                        ensure_ascii=False,
                    )
                ),
            ],
        )

    def summarize_graph_query(
        self,
        *,
        query: str,
        rewritten_query: str,
        entities: list[dict],
        reports: list[dict],
        fallback: str,
    ) -> str:
        if not self.chat_ready():
            return fallback
        return self._invoke_text(
            [
                SystemMessage(
                    content=(
                        "你是 GraphRAG 查询助手。"
                        "请基于给定实体、关系社区摘要回答问题。"
                        "不能编造图谱中没有的结论。"
                    )
                ),
                HumanMessage(
                    content=json.dumps(
                        {
                            "query": query,
                            "rewritten_query": rewritten_query,
                            "entities": entities[:8],
                            "reports": reports[:4],
                        },
                        ensure_ascii=False,
                    )
                ),
            ],
            fallback=fallback,
        )

    def _build_follow_up_messages(
        self,
        *,
        topic_type: str,
        conversation: list[str],
        slots: dict[str, str],
        missing_slots: list[str],
        risk_alerts: list[str],
        references: list[ReferenceCard],
        fallback: str,
    ) -> list[BaseMessage]:
        return [
            SystemMessage(
                content=(
                    "你是资深网站专题 PM 助手。"
                    "你的任务是润色一段已经确定事实的中文追问文案。"
                    "禁止新增、删除或改写任何事实项。只优化表达。"
                )
            ),
            HumanMessage(
                content=json.dumps(
                    {
                        "topic_type": topic_type,
                        "conversation": conversation[-6:],
                        "slots": slots,
                        "missing_slots": missing_slots,
                        "risk_alerts": risk_alerts,
                        "references": [item.title for item in references[:4]],
                        "draft": fallback,
                    },
                    ensure_ascii=False,
                )
            ),
        ]

    def _invoke_text(self, messages: list[BaseMessage], *, fallback: str) -> str:
        try:
            response = self.chat_model.invoke(messages)
            content = self._normalize_content(getattr(response, "content", ""))
            return content.strip() or fallback
        except Exception:
            return fallback

    def _stream_text(self, messages: list[BaseMessage], *, fallback: str) -> Iterable[str]:
        content = self._invoke_text(messages, fallback=fallback)
        for chunk in self._chunk_text(content):
            yield chunk

    def _invoke_json(self, *, model: type[T], fallback: T, messages: list[BaseMessage]) -> T:
        try:
            response = self.chat_model.invoke(messages)
            content = self._normalize_content(getattr(response, "content", ""))
            payload = self._extract_json_payload(content)
            return model.model_validate(payload)
        except Exception:
            return fallback

    def _extract_json_payload(self, text: str) -> dict:
        cleaned = text.strip()
        if "```" in cleaned:
            cleaned = cleaned.split("```", 2)[1]
            cleaned = cleaned.removeprefix("json").strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end >= start:
            cleaned = cleaned[start : end + 1]
        return json.loads(cleaned)

    def _normalize_content(self, content: object) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    if "text" in item and isinstance(item["text"], str):
                        parts.append(item["text"])
                    elif item.get("type") == "text" and isinstance(item.get("text"), str):
                        parts.append(item["text"])
            return "".join(parts)
        return str(content or "")

    def _fallback_route(self, text: str) -> str:
        lowered = text.lower()
        if any(keyword in lowered for keyword in ["招聘", "招募", "岗位", "校招", "社招", "投递"]):
            return "recruitment"
        if any(keyword in lowered for keyword in ["版本", "展示", "宣传", "落地页", "官网"]):
            return "display"
        return "activity"

    def _chunk_text(self, content: str, size: int = 20) -> Iterable[str]:
        text = content.strip()
        if not text:
            return
        for index in range(0, len(text), size):
            yield text[index : index + size]


llm_service = LlmService()
