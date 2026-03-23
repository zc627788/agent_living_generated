"""Qdrant 向量库访问层。"""

from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchAny,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.core.config import settings


class VectorStoreService:
    def __init__(self) -> None:
        self.client = QdrantClient(
            url=settings.qdrant_url,
            timeout=30.0,
            check_compatibility=False,
        )
        self.collection_name = settings.qdrant_collection

    def collection_exists(self) -> bool:
        return self.client.collection_exists(self.collection_name)

    def recreate_collection(self, vector_size: int) -> None:
        if self.collection_exists():
            self.client.delete_collection(self.collection_name)
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    def ensure_collection(self, vector_size: int) -> None:
        if not self.collection_exists():
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )

    def delete_collection(self) -> None:
        if self.collection_exists():
            self.client.delete_collection(self.collection_name)

    def upsert_points(self, points: list[PointStruct]) -> None:
        if points:
            self.client.upsert(collection_name=self.collection_name, points=points, wait=True)

    def delete_points_by_document_ids(self, document_ids: list[str]) -> None:
        if not document_ids or not self.collection_exists():
            return
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchAny(any=document_ids),
                        )
                    ]
                )
            ),
            wait=True,
        )

    def search(
        self,
        query_vector: list[float],
        topic_type: str,
        limit: int,
        document_ids: list[str] | None = None,
    ) -> list[Any]:
        if not self.collection_exists():
            return []

        # 先按专题标签和文档范围过滤，避免不同知识域之间互相串味。
        must_conditions: list[FieldCondition] = []
        if topic_type:
            must_conditions.append(
                FieldCondition(
                    key="tags",
                    match=MatchValue(value=topic_type),
                )
            )
        if document_ids:
            must_conditions.append(
                FieldCondition(
                    key="document_id",
                    match=MatchAny(any=document_ids),
                )
            )

        query_filter = Filter(must=must_conditions) if must_conditions else None
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return response.points


vector_store_service = VectorStoreService()
