"""会话（session）领域服务

封装 :class:`app.models.session.Conversation` 的全部 ORM 操作，并把数据库
行转换为 API 边界 DTO（:mod:`app.schemas.session`）。

约定：
- 服务方法**不**自动 commit，由调用方（路由层 / chat 流式端点）控制事务
  边界，便于把多次写入合并为同一个事务（例如 chat 端点连续 append
  user + assistant 两条消息）。
- 时间戳统一以 ``datetime.now(timezone.utc)`` 填充，避免依赖 SQLAlchemy
  的 ``onupdate=func.now()`` 在 SQLite 上的不可靠行为。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.session import Conversation
from app.schemas.session import (
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
    ConversationUpdate,
    DeleteResult,
    MessageAppend,
    MessageItem,
)


def _now() -> datetime:
    """统一的 UTC 时间戳"""
    return datetime.now(timezone.utc)


def _ensure_dt(value: Optional[datetime]) -> datetime:
    """从 DB 取出的时间戳有时是 ``datetime`` 有时是 ``str``，归一化"""
    if value is None:
        return _now()
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return _now()


def _to_message_item(raw: dict) -> MessageItem:
    """把 ``Conversation.messages`` JSON 中的 dict 转为 ``MessageItem``"""
    return MessageItem.model_validate(raw)


def _to_detail(conv: Conversation) -> ConversationDetail:
    raw_messages = conv.messages or []
    messages = [_to_message_item(m) for m in raw_messages]
    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        messages=messages,
        message_count=len(messages),
        created_at=_ensure_dt(conv.created_at),
        updated_at=_ensure_dt(conv.updated_at),
    )


def _to_summary(conv: Conversation) -> ConversationSummary:
    return ConversationSummary(
        id=conv.id,
        title=conv.title,
        message_count=len(conv.messages) if conv.messages else 0,
        created_at=_ensure_dt(conv.created_at),
        updated_at=_ensure_dt(conv.updated_at),
    )


def _generate_conversation_id() -> str:
    return f"conv_{uuid.uuid4().hex[:12]}"


class SessionService:
    """会话领域服务。所有方法都不自动 commit。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def list_summaries(self) -> List[ConversationSummary]:
        """按 updated_at 倒序返回所有会话摘要"""
        rows = (
            self.db.query(Conversation)
            .order_by(Conversation.updated_at.desc())
            .all()
        )
        return [_to_summary(r) for r in rows]

    def get_detail(self, conversation_id: str) -> Optional[ConversationDetail]:
        row = (
            self.db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .one_or_none()
        )
        return _to_detail(row) if row else None

    # ------------------------------------------------------------------
    # 创建
    # ------------------------------------------------------------------
    def create(self, payload: ConversationCreate) -> ConversationSummary:
        """创建新会话。若 ``conversation_id`` 已存在则复用该行（幂等）。"""
        new_id = payload.conversation_id or _generate_conversation_id()
        existing = (
            self.db.query(Conversation)
            .filter(Conversation.id == new_id)
            .one_or_none()
        )
        if existing is not None:
            return _to_summary(existing)

        now = _now()
        conv = Conversation(
            id=new_id,
            title=payload.title or "新对话",
            messages=[],
            created_at=now,
            updated_at=now,
        )
        self.db.add(conv)
        self.db.flush()  # 让 created_at / updated_at 触发 server_default
        return _to_summary(conv)

    # ------------------------------------------------------------------
    # 更新（仅标题）
    # ------------------------------------------------------------------
    def update_title(
        self, conversation_id: str, payload: ConversationUpdate
    ) -> Optional[ConversationDetail]:
        row = (
            self.db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .one_or_none()
        )
        if row is None:
            return None

        if payload.title is not None:
            row.title = payload.title
        row.updated_at = _now()
        self.db.flush()
        return _to_detail(row)

    # ------------------------------------------------------------------
    # 追加消息
    # ------------------------------------------------------------------
    def ensure_exists(self, conversation_id: str) -> Conversation:
        """chat 端点调用：若会话不存在则自动创建"""
        row = (
            self.db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .one_or_none()
        )
        if row is not None:
            return row

        now = _now()
        row = Conversation(
            id=conversation_id,
            title="新对话",
            messages=[],
            created_at=now,
            updated_at=now,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def append_message(
        self, conversation_id: str, msg: MessageAppend
    ) -> Optional[ConversationDetail]:
        """向指定会话追加一条消息，返回最新详情。

        若 ``conversation_id`` 不存在，**不会**自动创建；调用方应使用
        :meth:`ensure_exists` 自行决定是否创建。
        """
        row = self.ensure_exists(conversation_id)

        item = _to_message_item(
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": (msg.timestamp or _now()).isoformat(),
                "sources": msg.sources,
                "skill_used": msg.skill_used,
            }
        )
        existing = list(row.messages or [])
        existing.append(item.model_dump(mode="json", exclude_none=True))
        row.messages = existing
        row.updated_at = _now()
        # 首条 user 消息写入后自动改写默认标题
        if msg.role == "user":
            self._auto_derive_title(row)
        self.db.flush()
        return _to_detail(row)

    def derive_title_from_first_user_message(self, conversation_id: str) -> None:
        """如果当前标题还是默认 "新对话" 且已收到首条用户消息，则改写标题

        仍保留为公开方法，便于 chat endpoint 在一次事务末尾再保险一次。
        """
        row = (
            self.db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .one_or_none()
        )
        if row is None:
            return
        self._auto_derive_title(row)
        self.db.flush()

    def _auto_derive_title(self, row: Conversation) -> None:
        """单行改写（不提交、不 flush），便于 ``append_message`` 复用"""
        if row.title != "新对话":
            return
        first_user = next(
            (m for m in (row.messages or []) if m.get("role") == "user"),
            None,
        )
        if not first_user:
            return
        content = (first_user.get("content") or "").strip()
        if not content:
            return
        row.title = content[:20] + ("..." if len(content) > 20 else "")

    # ------------------------------------------------------------------
    # 删除
    # ------------------------------------------------------------------
    def delete(self, conversation_id: str) -> Optional[DeleteResult]:
        row = (
            self.db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .one_or_none()
        )
        if row is None:
            return None
        self.db.delete(row)
        self.db.flush()
        return DeleteResult(message="会话已删除", id=conversation_id)
