"""联网搜索模块 — 基于 Tavily Search API"""
import logging
from typing import Optional

from tavily import TavilyClient

from app.core.config import settings

logger = logging.getLogger(__name__)

# 全局 Tavily 客户端（懒加载）
_tavily_client: Optional[TavilyClient] = None


def _get_tavily_client() -> TavilyClient:
    """获取 Tavily 客户端实例（单例模式）"""
    global _tavily_client
    if _tavily_client is None:
        _tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    return _tavily_client


# 需要联网搜索的关键词触发列表
_WEB_SEARCH_KEYWORDS = [
    "最新", "今天", "当前", "实时", "现在", "行情", "价格", "走势",
    "天气", "预报", "灾情", "突发", "近期", "本周", "本月",
    "市场", "供需", "涨跌", "报价", "收购价", "批发价",
    "latest", "today", "current", "real-time", "price", "market",
    "weather", "forecast", "news",
]


def should_trigger_web_search(query: str, local_confidence: float = 1.0) -> bool:
    """判断是否需要触发联网搜索

    触发条件（满足任一）：
    1. 用户问题包含实时性/联网搜索关键词
    2. 本地 RAG 检索置信度不足（低于 0.6）

    Args:
        query: 用户查询文本
        local_confidence: 本地 RAG 检索的置信度（0.0-1.0）

    Returns:
        是否需要联网搜索
    """
    # 条件1：关键词触发
    query_lower = query.lower()
    keyword_triggered = any(kw in query_lower for kw in _WEB_SEARCH_KEYWORDS)

    # 条件2：本地置信度不足
    confidence_triggered = local_confidence < 0.6

    if keyword_triggered:
        logger.info(f"联网搜索[关键词触发]: '{query[:50]}...'")
    if confidence_triggered:
        logger.info(f"联网搜索[置信度触发]: confidence={local_confidence}")

    return keyword_triggered or confidence_triggered


async def web_search(query: str, max_results: int = 5) -> tuple[str, list[str]]:
    """执行联网搜索

    使用 Tavily Search API 进行实时网络搜索，获取最新的农业资讯。

    Args:
        query: 搜索查询文本
        max_results: 最大返回结果数

    Returns:
        (搜索结果文本, 引用来源URL列表)
    """
    try:
        client = _get_tavily_client()

        # 执行搜索
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",  # 使用高级搜索获取更详细结果
            include_raw_content=False,
            topic="general",
        )

        # 解析结果
        context_parts = []
        sources = []

        for result in response.get("results", []):
            title = result.get("title", "")
            content = result.get("content", "")
            url = result.get("url", "")

            if content:
                context_parts.append(f"【{title}】{content}")
            if url:
                sources.append(url)

        context = "---".join(context_parts) if context_parts else ""

        logger.info(
            f"联网搜索完成: 查询='{query[:30]}...', "
            f"结果数={len(context_parts)}, 来源数={len(sources)}"
        )

        return context, sources

    except Exception as e:
        logger.error(f"联网搜索异常: {e}")
        return "", []
