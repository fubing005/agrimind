
"""AgriMind - 农知睿策 FastAPI 入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.database import init_db

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="基于 AI 智能体架构的专业农业知识问答与决策支持系统",
    version="0.1.0",
)

# 初始化数据库
init_db()

# CORS 中间件配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["健康检查"])
async def health_check():
    return {"status": "ok", "service": settings.PROJECT_NAME}
