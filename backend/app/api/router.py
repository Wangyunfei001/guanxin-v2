"""API 路由聚合模块。"""

from fastapi import APIRouter

from app.api.agent import router as agent_router
from app.api.aisdk import router as aisdk_router
from app.api.a2ui import router as a2ui_router
from app.api.auth import router as auth_router
from app.api.knowledge import router as knowledge_router
from app.api.mcp import router as mcp_router
from app.api.skill import router as skill_router

api_router = APIRouter(prefix="/api")

# 注册子路由
api_router.include_router(auth_router)
api_router.include_router(knowledge_router)
api_router.include_router(agent_router)
api_router.include_router(aisdk_router)
api_router.include_router(skill_router)
api_router.include_router(mcp_router)
api_router.include_router(a2ui_router)
