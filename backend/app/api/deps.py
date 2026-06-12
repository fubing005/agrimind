"""AgriMind API 依赖注入"""
import uuid
from typing import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.agent.graph import agrimind_graph
from app.core.database import get_db
from app.services.session_service import SessionService


def get_conversation_id(conversation_id: str | None = None) -> str:
    """获取或生成对话会话 ID

    - 若调用方传入了非空 ``conversation_id``，原样返回
    - 否则生成一个 ``conv_xxxx`` 形式的 ID

    该函数不直接作为 FastAPI 依赖使用，而是被路由层显式调用。
    """
    if conversation_id:
        return conversation_id
    return f"conv_{uuid.uuid4().hex[:12]}"


def get_agent_graph():
    """获取 LangGraph 工作流实例"""
    return agrimind_graph


def get_session_service(db: Session = Depends(get_db)) -> SessionService:
    """FastAPI 依赖：返回当前请求的 SessionService 实例"""
    return SessionService(db)


# 重新导出 get_db 以便路由层 import 集中
__all__ = [
    "get_agent_graph",
    "get_conversation_id",
    "get_db",
    "get_session_service",
]
