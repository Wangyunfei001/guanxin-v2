"""观心 v2 应用入口模块。

创建 FastAPI 应用，注册路由、中间件，
在 lifespan 中初始化预设用户、ChromaDB、技能注册表和种子数据。
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings
from app.core.database import get_chroma_client
from app.core.sqlite import initialize_database
from app.core.checkpoints import close_checkpointer, initialize_checkpointer
from app.core.deps import init_preset_users
from app.core.middleware import RequestContextMiddleware
from app.core.responses import success
from app.skills.registry import get_skill_registry

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    logger.info("=== 观心 v2 启动中 ===")

    # 1. 初始化预设用户
    logger.info("Initializing preset users...")
    init_preset_users()

    # 2. 初始化 ChromaDB
    logger.info("Initializing SQLite business database...")
    initialize_database()

    logger.info("Initializing LangGraph checkpoints...")
    await initialize_checkpointer()
    from app.services.workflow_store import get_workflow_store

    recovered = get_workflow_store().recover_inflight()
    if recovered:
        logger.warning("Recovered %s interrupted workflow step(s)", recovered)

    from app.services.research_store import get_research_store

    recovered_research = get_research_store().recover_inflight()
    if recovered_research:
        logger.warning(
            "Marked %s interrupted research run(s) for manual resume",
            recovered_research,
        )

    # 3. 初始化 ChromaDB
    logger.info("Initializing ChromaDB...")
    get_chroma_client()

    # Embedding provider 连通性检查（不阻止启动，仅告警）
    logger.info("Checking %s embedding connectivity...", settings.embedding_provider)
    try:
        from app.services.embedding_service import get_embedding_service

        embedding_service = get_embedding_service()
        if embedding_service.check_connectivity():
            logger.info("%s Embedding 连通性正常", embedding_service.provider)
        else:
            if embedding_service.provider == "openai":
                logger.warning(
                    "OpenAI 兼容 Embedding 不可用，"
                    "将回退到本地伪随机向量。"
                )
            else:
                logger.warning(
                    "%s Embedding 不可用；知识库不会写入随机向量。",
                    embedding_service.provider,
                )
    except Exception as e:
        logger.warning("Embedding API 连通性检查异常，将继续启动: %s", e)

    # 4. 注册技能
    logger.info("Registering skills...")
    skill_registry = get_skill_registry()
    skill_registry.register_all()
    logger.info(f"Registered {len(skill_registry.list_skills())} skills")

    # 5. 初始化种子数据
    logger.info("Initializing seed data...")
    try:
        from app.seed.init_data import init_seed_data

        await init_seed_data()
    except Exception as e:
        logger.error(f"Seed data initialization failed: {e}")

    logger.info("=== 观心 v2 启动完成 ===")

    yield

    logger.info("=== 观心 v2 关闭 ===")
    await close_checkpointer()


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例。"""
    app = FastAPI(
        title=settings.app_name,
        description="AI Agent 全栈 Demo 系统",
        version="0.1.0",
        lifespan=lifespan,
    )

    # 中间件
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 路由
    app.include_router(api_router)

    # 健康检查
    @app.get("/health")
    async def health_check():
        """健康检查端点。"""
        return success({"status": "ok", "service": settings.app_name})

    # 根路径
    @app.get("/")
    async def root():
        """根路径。"""
        return success(
            {
                "service": settings.app_name,
                "version": "0.1.0",
                "docs": "/docs",
                "health": "/health",
            }
        )

    return app


# 全局应用实例
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "development",
    )
