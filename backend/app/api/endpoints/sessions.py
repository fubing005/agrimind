"""会话管理 API 端点

所有路由都走 :class:`app.services.session_service.SessionService`，
路由层只做参数解析、状态码映射、错误处理，保持薄。
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_session_service
from app.schemas.session import (
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
    ConversationUpdate,
    DeleteResult,
    MessageAppend,
)
from app.services.session_service import SessionService

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# 列表 / 创建 —— 静态路径必须放在 ``{conversation_id}`` 通配路径之前
# ---------------------------------------------------------------------------
@router.get(
    "",
    response_model=List[ConversationSummary],
    summary="获取所有会话列表",
)
def list_conversations(
    service: SessionService = Depends(get_session_service),
) -> List[ConversationSummary]:
    try:
        return service.list_summaries()
    except Exception as e:
        logger.error("获取会话列表失败: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取会话列表失败",
        )


@router.post(
    "",
    response_model=ConversationSummary,
    status_code=status.HTTP_201_CREATED,
    summary="创建新会话",
)
def create_conversation(
    payload: ConversationCreate,
    service: SessionService = Depends(get_session_service),
) -> ConversationSummary:
    """创建或幂等获取会话。

    - 同一 ``conversation_id`` 重复 POST 会返回已有记录（避免重复建行）
    - 标题为空时使用 ``"新对话"``
    """
    try:
        summary = service.create(payload)
        service.db.commit()
        return summary
    except Exception as e:
        service.db.rollback()
        logger.error("创建会话失败: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建会话失败",
        )


# ---------------------------------------------------------------------------
# 子路径必须先注册（FastAPI 按声明顺序匹配）
# ---------------------------------------------------------------------------
@router.post(
    "/{conversation_id}/messages",
    response_model=ConversationDetail,
    summary="向会话追加一条消息（内部接口）",
)
def append_message(
    payload: MessageAppend,
    conversation_id: str = Path(..., max_length=50),
    service: SessionService = Depends(get_session_service),
) -> ConversationDetail:
    """chat 流式端点专用：把 user / assistant 消息写入 DB"""
    try:
        detail = service.append_message(conversation_id, payload)
        if detail is None:
            service.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在",
            )
        service.db.commit()
        return detail
    except HTTPException:
        raise
    except Exception as e:
        service.db.rollback()
        logger.error("追加消息失败: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="追加消息失败",
        )


# ---------------------------------------------------------------------------
# ``{conversation_id}`` 通配路径
# ---------------------------------------------------------------------------
@router.get(
    "/{conversation_id}",
    response_model=ConversationDetail,
    summary="获取指定会话详情",
)
def get_conversation(
    conversation_id: str = Path(..., max_length=50),
    service: SessionService = Depends(get_session_service),
) -> ConversationDetail:
    detail = service.get_detail(conversation_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在",
        )
    return detail


@router.patch(
    "/{conversation_id}",
    response_model=ConversationDetail,
    summary="更新会话（仅标题）",
)
def update_conversation(
    payload: ConversationUpdate,
    conversation_id: str = Path(..., max_length=50),
    service: SessionService = Depends(get_session_service),
) -> ConversationDetail:
    try:
        detail = service.update_title(conversation_id, payload)
        if detail is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在",
            )
        service.db.commit()
        return detail
    except HTTPException:
        raise
    except Exception as e:
        service.db.rollback()
        logger.error("更新会话失败: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新会话失败",
        )


@router.delete(
    "/{conversation_id}",
    response_model=DeleteResult,
    summary="删除指定会话",
)
def delete_conversation(
    conversation_id: str = Path(..., max_length=50),
    service: SessionService = Depends(get_session_service),
) -> DeleteResult:
    try:
        result = service.delete(conversation_id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在",
            )
        service.db.commit()
        return result
    except HTTPException:
        raise
    except Exception as e:
        service.db.rollback()
        logger.error("删除会话失败: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除会话失败",
        )
