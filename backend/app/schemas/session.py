"""会话（session）相关的 Pydantic 数据校验模型

与 :mod:`app.schemas.chat` 解耦：chat 的 ``ChatMessage`` 是工作流内部
消息载体；本模块的 ``MessageItem`` 是 API 边界 DTO，结构与数据库
``Conversation.messages`` JSON 一致。
"""
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 单条消息
# ---------------------------------------------------------------------------
class MessageItem(BaseModel):
    """会话中的一条消息（API 边界 DTO）

    字段顺序与命名遵循 :class:`app.models.session.Conversation` 中
    ``messages`` JSON 的存储格式，避免一次额外的字段重命名。
    """

    role: Literal["user", "assistant", "system"] = Field(
        description="消息角色",
    )
    content: str = Field(
        min_length=1,
        max_length=8000,
        description="消息文本内容",
    )
    timestamp: Optional[datetime] = Field(
        default=None,
        description="消息时间戳（UTC）。未提供时由服务端填充。",
    )
    sources: Optional[List[str]] = Field(
        default=None,
        description="引用的参考文献/数据来源（仅 assistant 消息）",
    )
    skill_used: Optional[str] = Field(
        default=None,
        description="使用的技能名称（pest_expert / fertilizer_calc / market_analyzer）",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "role": "user",
                    "content": "水稻田里出现了稻飞虱，该怎么防治？",
                },
                {
                    "role": "assistant",
                    "content": "针对稻飞虱的防治，建议采取以下措施...",
                    "sources": ["《病虫害防治指南》p.45", "中国农业网"],
                    "skill_used": "pest_expert",
                },
            ]
        }
    }


class MessageAppend(BaseModel):
    """向会话追加一条消息（内部接口，chat 流式端点调用）"""

    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1, max_length=8000)
    timestamp: Optional[datetime] = None
    sources: Optional[List[str]] = None
    skill_used: Optional[str] = None


# ---------------------------------------------------------------------------
# 会话 CRUD
# ---------------------------------------------------------------------------
class ConversationCreate(BaseModel):
    """创建会话请求体

    - ``title`` 可选，默认值在 service 层补齐
    - ``conversation_id`` 可选；为空时由服务端生成
    """

    title: Optional[str] = Field(
        default=None,
        max_length=200,
        description="会话标题（为空时使用默认 \"新对话\"）",
    )
    conversation_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="客户端预生成的会话 ID（为空时由服务端生成）",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "水稻种植咨询",
                    "conversation_id": "conv_2025_06_11_001",
                }
            ]
        }
    }


class ConversationUpdate(BaseModel):
    """更新会话（当前仅支持修改标题）"""

    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="新的会话标题",
    )

    model_config = {
        "json_schema_extra": {"examples": [{"title": "小麦施肥方案讨论"}]}
    }


class ConversationSummary(BaseModel):
    """会话列表项（不含完整消息）"""

    id: str
    title: str
    message_count: int = Field(ge=0, description="消息条数")
    created_at: datetime
    updated_at: datetime


class ConversationDetail(BaseModel):
    """会话详情（含完整消息列表）"""

    id: str
    title: str
    messages: List[MessageItem] = Field(default_factory=list)
    message_count: int = Field(ge=0, description="消息条数")
    created_at: datetime
    updated_at: datetime

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "conv_2025_06_11_001",
                    "title": "水稻种植咨询",
                    "messages": [
                        {
                            "role": "user",
                            "content": "水稻田里出现了稻飞虱，该怎么防治？",
                        },
                        {
                            "role": "assistant",
                            "content": "针对稻飞虱的防治，建议采取以下措施...",
                            "sources": ["《病虫害防治指南》p.45"],
                            "skill_used": "pest_expert",
                        },
                    ],
                    "message_count": 2,
                    "created_at": "2025-06-11T08:30:00Z",
                    "updated_at": "2025-06-11T08:31:15Z",
                }
            ]
        }
    }


class DeleteResult(BaseModel):
    """删除操作的统一响应"""

    message: str
    id: str
