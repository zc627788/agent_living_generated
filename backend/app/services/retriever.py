"""混合检索服务。

向量召回负责找相似文本，关键词加权负责拉高业务强相关命中，邻接切片回补负责保持上下文完整。
"""

from __future__ import annotations

import re

from app.db.database import database
from app.models.schemas import ReferenceCard, RetrievalOptions
from app.services.llm_service import llm_service
from app.services.vector_store import vector_store_service

TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


class QdrantHybridRetriever:
    def search(
        self,
        query: str,
        topic_type: str,
        retrieval: RetrievalOptions | int | None = None,
    ) -> list[ReferenceCard]:
        _, results = self.search_with_diagnostics(query, topic_type, retrieval)
        return results

    def search_with_diagnostics(
        self,
        query: str,
        topic_type: str,
        retrieval: RetrievalOptions | int | None = None,
    ) -> tuple[str, list[ReferenceCard]]:
        """返回重写后的 query 与最终参考卡片，便于前端调试检索链路。"""
        if not query.strip():
            return "", []

        options = self._coerce_options(retrieval)
        rewritten_query = query.strip()
        if options.use_query_rewrite:
            rewritten_query = llm_service.rewrite_query(query, topic_type)

        query_vector = llm_service.embed_query(rewritten_query)
        candidate_limit = max(options.limit, options.limit * options.candidate_multiplier)
        points = vector_store_service.search(
            query_vector=query_vector,
            topic_type=topic_type,
            limit=candidate_limit,
            document_ids=options.document_ids,
        )

        query_tokens = tokenize(rewritten_query)
        ranked: list[tuple[float, dict]] = []
        for point in points:
            payload = point.payload or {}
            base_score = float(point.score or 0.0)
            title = str(payload.get("title", ""))
            section_path = str(payload.get("section_path", ""))
            content = str(payload.get("content", ""))
            tags = [str(tag).lower() for tag in payload.get("tags", [])]

            keyword_hits = sum(1 for token in set(query_tokens) if token in content.lower())
            title_hits = sum(1 for token in set(query_tokens) if token in title.lower())
            section_hits = sum(1 for token in set(query_tokens) if token in section_path.lower())
            tag_bonus = 0.04 if topic_type and topic_type.lower() in tags else 0.0

            score = (
                base_score
                + keyword_hits * options.keyword_weight
                + title_hits * (options.keyword_weight * 1.5)
                + section_hits * (options.keyword_weight * 0.8)
                + tag_bonus
            )
            if score < options.min_score:
                continue

            ranked.append((score, payload))

        ranked.sort(key=lambda item: item[0], reverse=True)
        cards: list[ReferenceCard] = []
        for score, payload in ranked[: options.limit]:
            chunk_id = str(payload.get("id", payload.get("document_id")))
            context = database.get_chunk_context(chunk_id, neighbor_hops=options.neighbor_hops)
            snippet = context["combined_content"] if context else str(payload.get("content", ""))
            cards.append(
                ReferenceCard(
                    id=chunk_id,
                    title=str(payload.get("title", "未命名文档")),
                    source=str(payload.get("source", "未知来源")),
                    source_type=str(payload.get("source_type", "knowledge")),
                    snippet=snippet[:320].replace("\n", " ").strip(),
                    url=payload.get("url"),
                    thumbnail_url=payload.get("thumbnail_url"),
                    score=round(score, 3),
                    section_path=str(payload.get("section_path", "概览")),
                    tags=list(payload.get("tags", [])),
                )
            )
        return rewritten_query, cards

    def _coerce_options(self, retrieval: RetrievalOptions | int | None) -> RetrievalOptions:
        if isinstance(retrieval, RetrievalOptions):
            return retrieval
        if isinstance(retrieval, int):
            return RetrievalOptions(limit=retrieval)
        return RetrievalOptions()


retriever = QdrantHybridRetriever()
