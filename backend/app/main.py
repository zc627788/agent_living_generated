"""FastAPI 应用入口。

负责组装路由、中间件与生命周期钩子，让数据库、知识库和后台任务在应用启动时就进入可用状态。
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import settings
from app.db.database import database
from app.services.knowledge_jobs import knowledge_job_service
from app.services.knowledge_base import knowledge_base_service


def create_app() -> FastAPI:
    """创建并配置 API 应用实例。"""
    app = FastAPI(
        title=settings.app_name,
        default_response_class=JSONResponse,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix=settings.api_prefix)

    @app.on_event("startup")
    def startup() -> None:
        # 启动时先完成表结构与内置知识文档准备，避免首个请求承担冷启动成本。
        database.initialize()
        knowledge_base_service.ensure_seeded()

    @app.on_event("shutdown")
    def shutdown() -> None:
        # 退出时主动关闭线程池和数据库连接，避免 Windows 下残留句柄。
        knowledge_job_service.close()
        database.close()

    return app


app = create_app()
