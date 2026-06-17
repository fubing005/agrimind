"""AgriMind 智能体状态定义与边界拦截器"""
from typing import Annotated, Optional
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field
from app.schemas.chat import GuardrailResult


class AgentState(BaseModel):
    """LangGraph 智能体全局状态

    该状态贯穿整个 LangGraph 工作流，在各节点之间传递。
    """

    # 对话消息历史（LangGraph 自动管理追加）
    messages: Annotated[list[BaseMessage], add_messages] = Field(
        default_factory=list,
        description="对话消息历史",
    )

    # 当前用户输入
    user_input: str = Field(
        default="",
        description="当前用户输入的原始消息",
    )

    # 会话ID
    conversation_id: str = Field(
        default="",
        description="对话会话唯一标识",
    )

    # 边界拦截结果
    guardrail_result: Optional[GuardrailResult] = Field(
        default=None,
        description="边界拦截器分类结果",
    )

    # 是否被拦截（非农业问题）
    blocked: bool = Field(
        default=False,
        description="是否被边界拦截器拦截",
    )

    # 本地 RAG 检索结果
    local_rag_context: Optional[str] = Field(
        default=None,
        description="本地知识库检索结果",
    )

    # 联网搜索结果
    web_search_context: Optional[str] = Field(
        default=None,
        description="联网搜索结果",
    )

    # 当前使用的技能
    active_skill: Optional[str] = Field(
        default=None,
        description="当前激活的农业技能名称",
    )

    # 技能输出结果
    skill_output: Optional[str] = Field(
        default=None,
        description="技能执行输出结果",
    )

    # 最终生成的回答
    final_answer: Optional[str] = Field(
        default=None,
        description="最终生成的回答内容",
    )

    # 引用来源
    sources: list[dict] = Field(
        default_factory=list,
        description="引用的参考文献/数据来源 — 每项含 title, url, source_type",
    )

    model_config = {"arbitrary_types_allowed": True}
