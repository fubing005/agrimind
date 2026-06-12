"""AgriMind API 总路由"""
from fastapi import APIRouter

from app.api.endpoints.chat import router as chat_router
from app.api.endpoints.knowledge import router as knowledge_router
from app.api.endpoints.sessions import router as sessions_router

api_router = APIRouter()

# 对话相关接口
api_router.include_router(chat_router, prefix="/chat", tags=["对话"])

# 知识库管理接口
api_router.include_router(knowledge_router, prefix="/knowledge", tags=["知识库"])

# 会话管理接口
api_router.include_router(sessions_router, prefix="/sessions", tags=["会话"])
