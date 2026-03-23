"""对象存储访问层。

当前默认接 MinIO，用于保存上传原文、GraphRAG 产物压缩包和导出的 DOCX。
"""

from __future__ import annotations

from io import BytesIO
from urllib.parse import urlsplit

from minio import Minio

from app.core.config import settings


class ObjectStorageService:
    def __init__(self) -> None:
        parsed = urlsplit(settings.minio_endpoint)
        secure = parsed.scheme == "https"
        endpoint = parsed.netloc or parsed.path
        self.client = Minio(
            endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=secure,
        )
        self.bucket = settings.minio_bucket

    def ensure_bucket(self) -> None:
        """按需创建 bucket，避免本地首次启动时报错。"""
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def upload_bytes(self, object_key: str, payload: bytes, content_type: str) -> str:
        self.ensure_bucket()
        self.client.put_object(
            bucket_name=self.bucket,
            object_name=object_key,
            data=BytesIO(payload),
            length=len(payload),
            content_type=content_type,
        )
        return object_key

    def delete_object(self, object_key: str) -> None:
        if not object_key:
            return
        self.ensure_bucket()
        try:
            self.client.remove_object(self.bucket, object_key)
        except Exception:
            return


object_storage_service = ObjectStorageService()
