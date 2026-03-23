"""集中管理项目运行配置。

这里统一读取 `.env`，并给数据库、向量库、对象存储和模型参数提供默认值。
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parents[3]
load_dotenv(ROOT_DIR / ".env", override=False)


class Settings(BaseModel):
    """运行期配置模型。"""
    app_name: str = "Web Topic Requirement Agent API"
    api_prefix: str = "/api/v1"
    project_root: Path = Path(__file__).resolve().parents[2]
    database_url: str = os.getenv(
        "POSTGRES_URL",
        f"sqlite:///{(Path(__file__).resolve().parents[2] / 'app' / 'storage' / 'mvp.sqlite3').as_posix()}",
    )
    db_path: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[2] / "app" / "storage" / "mvp.sqlite3"
    )
    knowledge_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[2] / "app" / "knowledge"
    )
    upload_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[2] / "app" / "storage" / "knowledge"
    )
    export_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[2] / "app" / "storage" / "exports"
    )
    graphrag_workspace_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[2] / "app" / "storage" / "graphrag"
    )
    rag_provider: str = os.getenv("RAG_PROVIDER", "qdrant_hybrid")
    dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
    qwen_base_url: str = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    qwen_chat_model: str = os.getenv("QWEN_CHAT_MODEL", "qwen3.5-flash")
    qwen_embedding_model: str = os.getenv("QWEN_EMBEDDING_MODEL", "text-embedding-v4")
    graphrag_api_base: str = os.getenv("GRAPHRAG_API_BASE", os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"))
    graphrag_chat_model: str = os.getenv("GRAPHRAG_CHAT_MODEL", os.getenv("QWEN_CHAT_MODEL", "qwen3.5-flash"))
    graphrag_embedding_model: str = os.getenv("GRAPHRAG_EMBEDDING_MODEL", os.getenv("QWEN_EMBEDDING_MODEL", "text-embedding-v4"))
    graphrag_vector_size: int = int(os.getenv("GRAPHRAG_VECTOR_SIZE", "1024"))
    qdrant_url: str = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "prd_agent_chunks")
    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "")
    minio_access_key: str = os.getenv("MINIO_ACCESS_KEY", "")
    minio_secret_key: str = os.getenv("MINIO_SECRET_KEY", "")
    minio_bucket: str = os.getenv("MINIO_BUCKET", "prd-agent")
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:3000",
            "http://localhost:3000",
        ]
    )


settings = Settings()
