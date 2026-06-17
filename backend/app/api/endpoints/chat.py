"""对话 API 端点 — 支持 SSE 流式输出

chat 端点会调用 :class:`app.services.session_service.SessionService` 把
user 与 assistant 消息持久化到 ``Conversation.messages``，使后端成为
会话与消息的单一真相源；前端不再需要（也不应该）在每个 SSE chunk
之后调 update 接口。
"""
import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session

from app.agent.guardrail import GUARDRAIL_BLOCKED_MESSAGE
from app.agent.graph import get_graph
from app.agent.state import AgentState
from app.api.deps import get_conversation_id, get_db
from app.schemas.chat import ChatMessage, ChatRequest, ChatResponse, MessageRole
from app.schemas.session import MessageAppend
from app.services.session_service import SessionService
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)
router = APIRouter()


def _persist_exchange(
    service: SessionService,
    conversation_id: str,
    user_message: str,
    result: dict,
) -> None:
    """把一轮问答（user + assistant）写入会话。

    把两条消息合并在同一个事务里，任一失败都会回滚，避免出现只写了
    user 但没写 assistant 的半截状态。
    """
    try:
        service.ensure_exists(conversation_id)

        service.append_message(
            conversation_id,
            MessageAppend(role="user", content=user_message),
        )

        if not result.get("blocked"):
            assistant_content = (result.get("final_answer") or "").strip()
            service.append_message(
                conversation_id,
                MessageAppend(
                    role="assistant",
                    content=assistant_content,
                    sources=result.get("sources") or None,
                    skill_used=result.get("active_skill"),
                ),
            )

        service.derive_title_from_first_user_message(conversation_id)
        service.db.commit()
    except Exception as e:
        service.db.rollback()
        # 持久化失败不能让 chat 接口 500；只记录日志，由前端 onError 处理
        logger.error("持久化会话消息失败: %s", e)


@router.post("/chat", response_model=ChatResponse, summary="对话接口（非流式）")
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    """非流式对话接口

    发送消息并等待完整回复。
    """
    conversation_id = get_conversation_id(request.conversation_id)
    service = SessionService(db)

    initial_state: AgentState = AgentState(
        messages=[HumanMessage(content=request.message)],
        user_input=request.message,
        conversation_id=conversation_id,
    )

    # thread_id 让 checkpointer 按 session 隔离/恢复记忆
    config: RunnableConfig = {"configurable": {"thread_id": conversation_id}}
    result = await get_graph().ainvoke(initial_state, config=config)
    _persist_exchange(service, conversation_id, request.message, result)

    blocked = bool(result.get("blocked"))
    final_answer = result.get("final_answer") or ""
    sources = result.get("sources") or []

    return ChatResponse(
        conversation_id=conversation_id,
        message=ChatMessage(
            role=MessageRole.ASSISTANT,
            content=final_answer,
            sources=sources or None,
            skill_used=result.get("active_skill"),
            timestamp=datetime.now(timezone.utc),
        ),
        blocked=blocked,
    )


@router.post("/chat/stream", summary="对话接口（SSE 流式）")
async def chat_stream(
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    """SSE 流式对话接口

    事件类型：
    - ``message``：回答内容片段
    - ``sources``：引用来源（JSON 数组字符串）
    - ``done``：回答完成（data 为 ``{conversation_id, skill_used}``）
    - ``blocked``：被边界拦截器拦截（data 为拦截文案）
    - ``error``：发生错误（data 为错误描述）
    """
    conversation_id = get_conversation_id(request.conversation_id)
    service = SessionService(db)

    async def event_generator():
        try:
            initial_state: AgentState = AgentState(
                messages=[HumanMessage(content=request.message)],
                user_input=request.message,
                conversation_id=conversation_id,
            )

            # thread_id 让 checkpointer 按 session 隔离/恢复记忆
            config: RunnableConfig = {"configurable": {"thread_id": conversation_id}}
            result = await get_graph().ainvoke(initial_state, config=config)
            # 立刻持久化这一轮问答，避免 SSE 中途断流导致消息丢失
            _persist_exchange(service, conversation_id, request.message, result)

            if result.get("blocked"):
                yield _format_sse("blocked", GUARDRAIL_BLOCKED_MESSAGE)
                yield _format_sse("done", "")
                return

            final_answer = result.get("final_answer") or ""
            sources = result.get("sources") or []

            # 流式输出回答内容（按段落/行 chunk，保留 markdown 结构完整性）
            # 以换行符为切分点，避免在 markdown 标记（如 ** 或 # ）中间截断
            chunk_size = 8  # 每次输出的字符数
            for i in range(0, len(final_answer), chunk_size):
                chunk = final_answer[i : i + chunk_size]
                yield _format_sse("message", chunk)
                await asyncio.sleep(0.02)  # 模拟流式延迟

            if sources:
                yield _format_sse("sources", json.dumps(sources, ensure_ascii=False))

            done_data = json.dumps(
                {
                    "conversation_id": conversation_id,
                    "skill_used": result.get("active_skill"),
                },
                ensure_ascii=False,
            )
            yield _format_sse("done", done_data)

        except Exception as e:
            logger.error("SSE 流式输出异常: %s", e)
            yield _format_sse("error", str(e))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _format_sse(event: str, data: str) -> str:
    """格式化 SSE 事件

    SSE 规范要求：
    - ``event:`` 和 ``data:`` 必须各自独占一行
    - 若 ``data`` 包含换行符，每一行都必须带 ``data:`` 前缀
    - 事件块之间以空行（``\\n\\n``）分隔
    """
    # 将 data 中的每一行都加上 "data: " 前缀，符合 SSE 规范
    data_lines = "".join(f"data: {line}\n" for line in data.split("\n"))
    return f"event: {event}\n{data_lines}\n"
