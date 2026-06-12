"""会话数据模型"""
from sqlalchemy import JSON, Column, DateTime, Integer, String, func

from app.core.database import Base


class Conversation(Base):
    """对话会话模型

    字段说明：
    - ``id``：前端生成或后端生成的会话唯一标识（字符串）
    - ``title``：会话标题（默认 "新对话"，首条用户消息到达后会被自动改写）
    - ``messages``：JSON 数组，每项形如
      ``{"role": "user"|"assistant"|"system", "content": str,
         "timestamp": ISO8601 str, "sources": list[str]?, "skill_used": str?}``
    - ``created_at`` / ``updated_at``：DB 端维护的 UTC 时间戳
    """

    __tablename__ = "conversations"

    id = Column(String(50), primary_key=True, index=True)
    title = Column(String(200), nullable=False, default="新对话")
    messages = Column(JSON, nullable=False, default=list)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
