"""AgriMind LangGraph 工作流定义

工作流节点：
1. guardrail — 边界拦截器（非农业问题拦截）
2. router — 路由决策（决定调用哪些检索/技能）
3. skill_router — 技能路由（判断是否需要调用特化技能）
4. pest_expert — 病虫害智能诊断
5. fertilizer_calc — 精准施肥决策
6. market_analyzer — 农产品行情分析
7. local_rag — 本地知识库检索（LlamaIndex + ChromaDB）
8. web_search — 联网搜索（Tavily）
9. generate — 最终回答生成
"""
import logging
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage

from app.core.config import settings
from app.agent.state import AgentState
from app.agent.guardrail import guardrail_node, GUARDRAIL_BLOCKED_MESSAGE
from app.agent.rag.local_rag import local_rag_search
from app.agent.rag.web_search import web_search, should_trigger_web_search
from app.agent.skills.pest_expert import pest_expert_skill, is_pest_related
from app.agent.skills.fertilizer import fertilizer_calc_skill, is_fertilizer_related
from app.agent.skills.market_trend import market_analyzer_skill, is_market_related
from pydantic import SecretStr

logger = logging.getLogger(__name__)

# 系统提示词
AGENT_SYSTEM_PROMPT = """你是「农知睿策」，一个专业的农业知识问答与决策支持AI助手。

你的职责：
1. 为用户提供精准、前沿、有据可查的农业技术解答
2. 只回答农业相关领域的问题
3. 回答时引用参考文献和数据来源

你具备以下专业技能：
- pest_expert: 病虫害智能诊断
- fertilizer_calc: 精准施肥配方计算
- market_analyzer: 农产品价格走势与供需分析

回答规范：
- 专业准确，有据可查
- 若引用了本地文档或网页，必须在文末附带 [参考文献/数据来源]
- 语言简洁清晰，适合农民和农业从业者理解
"""


def router_node(state: AgentState) -> dict:
    """路由决策节点

    根据拦截结果和问题类型，决定后续调用哪些节点。
    先经过技能路由判断，再进入 RAG 检索。

    Args:
        state: 当前智能体状态

    Returns:
        状态更新字典（路由不修改状态，仅用于条件分支）
    """
    if state.blocked:
        return {}
    logger.info(f"路由决策: conversation_id={state.conversation_id}")
    return {}


def _skill_router_decision(state: AgentState) -> str:
    """技能路由决策

    根据用户问题判断是否需要调用特化技能，以及调用哪个技能。
    优先级：pest_expert > fertilizer_calc > market_analyzer > local_rag

    Args:
        state: 当前智能体状态

    Returns:
        下一个节点名称
    """
    query = state.user_input

    if is_pest_related(query):
        logger.info("技能路由: → pest_expert")
        return "pest_expert"
    elif is_fertilizer_related(query):
        logger.info("技能路由: → fertilizer_calc")
        return "fertilizer_calc"
    elif is_market_related(query):
        logger.info("技能路由: → market_analyzer")
        return "market_analyzer"

    logger.info("技能路由: → local_rag（无特化技能匹配）")
    return "local_rag"


async def pest_expert_node(state: AgentState) -> dict:
    """病虫害智能诊断节点

    Args:
        state: 当前智能体状态

    Returns:
        状态更新字典
    """
    if state.blocked:
        return {}

    result = await pest_expert_skill(
        query=state.user_input,
        local_context=state.local_rag_context or "",
        web_context=state.web_search_context or "",
    )

    logger.info("病虫害诊断节点: 完成")
    return {
        "active_skill": "pest_expert",
        "skill_output": result,
    }


async def fertilizer_calc_node(state: AgentState) -> dict:
    """精准施肥决策节点

    Args:
        state: 当前智能体状态

    Returns:
        状态更新字典
    """
    if state.blocked:
        return {}

    result = await fertilizer_calc_skill(
        query=state.user_input,
        local_context=state.local_rag_context or "",
        web_context=state.web_search_context or "",
    )

    logger.info("施肥决策节点: 完成")
    return {
        "active_skill": "fertilizer_calc",
        "skill_output": result,
    }


async def market_analyzer_node(state: AgentState) -> dict:
    """农产品行情分析节点

    Args:
        state: 当前智能体状态

    Returns:
        状态更新字典
    """
    if state.blocked:
        return {}

    result = await market_analyzer_skill(
        query=state.user_input,
        local_context=state.local_rag_context or "",
    )

    # market_analyzer 内部已做联网搜索，合并来源
    logger.info("行情分析节点: 完成")
    return {
        "active_skill": "market_analyzer",
        "skill_output": result,
    }


async def local_rag_node(state: AgentState) -> dict:
    """本地知识库检索节点

    通过 LlamaIndex 从 ChromaDB 检索本地农业文献。

    Args:
        state: 当前智能体状态

    Returns:
        状态更新字典
    """
    if state.blocked:
        return {}

    context, sources = await local_rag_search(state.user_input)

    # 计算本地检索置信度（基于结果数量和内容长度）
    confidence = 0.0
    if context:
        confidence = min(1.0, len(context) / 500)  # 简单启发式

    logger.info(f"本地RAG节点: 置信度={confidence:.2f}, 来源={sources}")

    return {
        "local_rag_context": context if context else None,
        "sources": sources,
    }


async def web_search_node(state: AgentState) -> dict:
    """联网搜索节点

    使用 Tavily API 进行实时网络搜索。

    Args:
        state: 当前智能体状态

    Returns:
        状态更新字典
    """
    if state.blocked:
        return {}

    context, sources = await web_search(state.user_input)

    # 合并来源
    all_sources = list(state.sources) + sources

    logger.info(f"联网搜索节点: 来源数={len(sources)}")

    return {
        "web_search_context": context if context else None,
        "sources": all_sources,
    }


def _should_web_search(state: AgentState) -> str:
    """判断是否需要联网搜索

    Args:
        state: 当前智能体状态

    Returns:
        "web_search" 或 "generate"
    """
    # 计算本地检索置信度
    local_confidence = 0.0
    if state.local_rag_context:
        local_confidence = min(1.0, len(state.local_rag_context) / 500)

    # 判断是否需要联网搜索
    if should_trigger_web_search(state.user_input, local_confidence):
        return "web_search"

    return "generate"


async def generate_node(state: AgentState) -> dict:
    """最终回答生成节点

    根据检索结果和技能输出，调用 LLM 生成最终回答。

    Args:
        state: 当前智能体状态

    Returns:
        状态更新字典
    """
    # 如果被拦截，直接返回拒绝语
    if state.blocked:
        return {
            "final_answer": GUARDRAIL_BLOCKED_MESSAGE,
            "messages": [AIMessage(content=GUARDRAIL_BLOCKED_MESSAGE)],
        }

    # 构建上下文
    context_parts = []
    if state.local_rag_context:
        context_parts.append(f"【本地知识库检索结果】{state.local_rag_context}")
    if state.web_search_context:
        context_parts.append(f"【联网搜索结果】{state.web_search_context}")
    if state.skill_output:
        context_parts.append(f"【技能输出({state.active_skill})】{state.skill_output}")

    context = "".join(context_parts) if context_parts else "暂无额外检索上下文。"

    # 收集引用来源
    sources = list(state.sources) if state.sources else []

    try:
        llm = ChatOpenAI(
            api_key=SecretStr(settings.OPENAI_API_KEY),
            base_url=settings.OPENAI_BASE_URL,
            model=settings.OPENAI_MODEL,
            temperature=0.3,
        )

        messages: list[BaseMessage] = [
            SystemMessage(content=AGENT_SYSTEM_PROMPT),
        ]

        # 添加对话历史
        if state.messages:
            messages.extend(state.messages[-6:])  # 最近3轮对话

        # 添加当前问题和上下文
        user_message = f"用户问题：{state.user_input}参考上下文：{context}"
        if sources:
            user_message += f"数据来源：{', '.join(sources)}"
        messages.append(HumanMessage(content=user_message))

        response = await llm.ainvoke(messages)
        final_answer = response.content

        # 在回答末尾附加引用来源
        if sources:
            source_text = "---**[参考文献/数据来源]**"
            for i, src in enumerate(sources, 1):
                source_text += f"{i}. {src}"
            final_answer += source_text

        return {
            "final_answer": final_answer,
            "messages": [AIMessage(content=final_answer)],
            "sources": sources,
        }

    except Exception as e:
        logger.error(f"生成节点异常: {e}")
        error_msg = "抱歉，生成回答时遇到了问题，请稍后重试。"
        return {
            "final_answer": error_msg,
            "messages": [AIMessage(content=error_msg)],
        }


def _should_continue_after_guardrail(state: AgentState) -> str:
    """边界拦截后的条件路由

    Args:
        state: 当前智能体状态

    Returns:
        下一个节点名称
    """
    if state.blocked:
        return "generate"
    return "router"


def build_graph() -> CompiledStateGraph:
    """构建 AgriMind LangGraph 工作流图

    完整工作流：
    guardrail → (blocked?) → generate(拒绝语)
             → router → skill_router → (pest_expert / fertilizer_calc / market_analyzer / local_rag)
                        pest_expert → generate
                        fertilizer_calc → generate
                        market_analyzer → generate
                        local_rag → (需要联网?) → web_search → generate
                                             → generate

    Returns:
        编译后的 LangGraph 工作流
    """
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("guardrail", guardrail_node)
    graph.add_node("router", router_node)
    graph.add_node("pest_expert", pest_expert_node)
    graph.add_node("fertilizer_calc", fertilizer_calc_node)
    graph.add_node("market_analyzer", market_analyzer_node)
    graph.add_node("local_rag", local_rag_node)
    graph.add_node("web_search", web_search_node)
    graph.add_node("generate", generate_node)

    # 设置入口
    graph.set_entry_point("guardrail")

    # guardrail → blocked? → generate / router
    graph.add_conditional_edges(
        "guardrail",
        _should_continue_after_guardrail,
        {
            "generate": "generate",
            "router": "router",
        },
    )

    # router → 技能路由（条件分支到4个节点）
    graph.add_conditional_edges(
        "router",
        _skill_router_decision,
        {
            "pest_expert": "pest_expert",
            "fertilizer_calc": "fertilizer_calc",
            "market_analyzer": "market_analyzer",
            "local_rag": "local_rag",
        },
    )

    # 三个技能节点 → 直接生成
    graph.add_edge("pest_expert", "generate")
    graph.add_edge("fertilizer_calc", "generate")
    graph.add_edge("market_analyzer", "generate")

    # local_rag → 联网搜索? → generate
    graph.add_conditional_edges(
        "local_rag",
        _should_web_search,
        {
            "web_search": "web_search",
            "generate": "generate",
        },
    )
    graph.add_edge("web_search", "generate")

    # generate → END
    graph.add_edge("generate", END)

    return graph.compile()


# 全局工作流实例
agrimind_graph = build_graph()
