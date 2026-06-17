"""对话相关的 Pydantic 数据校验模型"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from enum import Enum


class SourceItem(BaseModel):
    """引用来源条目

    携带来源标题与可点击链接，前端可据此渲染为超链接。
    """

    title: str = Field(
        description="来源标题/文件名",
    )
    url: Optional[str] = Field(
        default=None,
        description="来源链接（网页 URL 或本地文件路径）",
    )
    source_type: Literal["web", "local"] = Field(
        description="来源类型：web=联网搜索, local=本地知识库",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"title": "中国农业网-稻飞虱防治", "url": "https://example.com/article", "source_type": "web"},
                {"title": "病虫害防治指南.pdf", "url": None, "source_type": "local"},
            ]
        }
    }


class MessageRole(str, Enum):
    """消息角色枚举"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatRequest(BaseModel):
    """用户对话请求"""
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="用户输入的消息内容",
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="对话会话ID，为空则创建新会话",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "水稻田里出现了稻飞虱，该怎么防治？",
                    "conversation_id": "conv_abc123",
                }
            ]
        }
    }


class GuardrailResult(BaseModel):
    """边界拦截结果"""
    is_agriculture: bool = Field(
        description="是否属于农业领域问题",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="分类置信度",
    )
    category: Optional[str] = Field(
        default=None,
        description="农业子类别（如：作物种植、病虫害防治、土壤肥力等）",
    )
    reason: Optional[str] = Field(
        default=None,
        description="分类理由",
    )


class ChatMessage(BaseModel):
    """单条对话消息"""
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    sources: Optional[list[SourceItem]] = Field(
        default=None,
        description="引用的参考文献/数据来源",
    )
    skill_used: Optional[str] = Field(
        default=None,
        description="使用的技能名称（pest_expert / fertilizer_calc / market_analyzer）",
    )


class ChatResponse(BaseModel):
    """对话响应（非流式）"""
    conversation_id: str = Field(description="对话会话ID")
    message: ChatMessage = Field(description="助手回复消息")
    blocked: bool = Field(default=False, description="是否被边界拦截器拦截")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "conversation_id": "conv_abc123",
                    "message": {
                        "role": "assistant",
                        "content": "针对稻飞虱的防治，建议采取以下措施...",
                        "sources": [
                        {"title": "《病虫害防治指南》p.45", "url": None, "source_type": "local"},
                        {"title": "中国农业网", "url": "https://www.farmer.com.cn/article/123", "source_type": "web"},
                    ],
                        "skill_used": "pest_expert",
                    },
                    "blocked": False,
                }
            ]
        }
    }


class SSEEvent(BaseModel):
    """SSE 流式事件数据"""
    event: str = Field(description="事件类型：message / done / error / blocked")
    data: str = Field(description="事件数据内容")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"event": "message", "data": "针对稻飞虱的防治"},
                {"event": "done", "data": ""},
                {"event": "blocked", "data": "我是农知睿策，我只能为您提供专业的农业相关知识解答。"},
            ]
        }
    }
