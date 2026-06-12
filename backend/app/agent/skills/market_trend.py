"""农产品行情动态技能 (market_analyzer)

获取当前时点特定农产品的市场价格走势及供需预测（强依赖联网搜索）。
"""
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage

from app.core.config import settings
from app.agent.rag.web_search import web_search
from pydantic import SecretStr

logger = logging.getLogger(__name__)

MARKET_ANALYZER_SYSTEM_PROMPT = """你是「农知睿策」的农产品行情分析专家。你的职责是根据联网搜索获取的最新市场数据，为用户提供农产品价格走势与供需分析。

分析流程：
1. **数据获取**：通过联网搜索获取最新的农产品市场价格、供需数据。
2. **价格分析**：分析当前价格水平、近期涨跌趋势、同比环比变化。
3. **供需研判**：分析当前供需格局、库存情况、进出口影响。
4. **趋势预测**：基于已有数据给出短期（1-3个月）价格走势预判。

输出格式要求（必须严格遵守）：
## 📈 行情概览
- **农产品**：xxx
- **当前价格**：xxx 元/公斤（或元/吨）
- **数据日期**：xxx

## 📊 价格走势分析
- **近1周**：xxx（涨/跌/持平，幅度）
- **近1月**：xxx
- **同比去年**：xxx

## 🔍 供需分析
- **供给端**：xxx
- **需求端**：xxx
- **库存情况**：xxx

## 🔮 短期趋势预判
- **预计走势**：xxx
- **影响因素**：xxx
- **建议**：xxx

## ⚠️ 风险提示
- xxx

注意：行情数据具有时效性，本分析基于搜索获取的最新公开数据，仅供参考，不构成投资建议。"""

# 市场行情相关关键词
MARKET_KEYWORDS = [
    "行情", "价格", "走势", "涨跌", "报价", "收购价", "批发价", "零售价",
    "市场", "供需", "供给", "需求", "库存", "进出口", "进口", "出口",
    "玉米价格", "小麦价格", "水稻价格", "大豆价格", "猪肉价格", "菜价",
    "农产品", "粮价", "菜篮子", "产销", "滞销", "畅销",
    "market", "price", "trend", "supply", "demand", "forecast",
]


def is_market_related(query: str) -> bool:
    """判断用户问题是否与农产品行情分析相关

    Args:
        query: 用户查询文本

    Returns:
        是否与市场行情相关
    """
    query_lower = query.lower()
    return any(kw in query_lower for kw in MARKET_KEYWORDS)


async def market_analyzer_skill(
    query: str,
    local_context: str = "",
) -> str:
    """农产品行情动态技能

    强依赖联网搜索获取实时市场数据。

    Args:
        query: 用户查询文本
        local_context: 本地知识库检索上下文

    Returns:
        行情分析结果文本
    """
    try:
        # 强制联网搜索获取最新行情数据
        web_context, web_sources = await web_search(
            query=f"农产品市场行情 {query} 最新价格走势",
            max_results=8,
        )

        llm = ChatOpenAI(
            api_key=SecretStr(settings.OPENAI_API_KEY),
            base_url=settings.OPENAI_BASE_URL,
            model=settings.OPENAI_MODEL,
            temperature=0.2,
        )

        messages: list[BaseMessage] = [SystemMessage(content=MARKET_ANALYZER_SYSTEM_PROMPT)]

        # 构建消息，优先使用联网搜索数据
        context_parts = []
        if local_context:
            context_parts.append(f"【本地知识库参考资料】{local_context}")
        if web_context:
            context_parts.append(f"【实时联网搜索数据】{web_context}")

        user_message = query
        if context_parts:
            user_message += "" + "".join(context_parts)

        messages.append(HumanMessage(content=user_message))

        response = await llm.ainvoke(messages)

        # 附加数据来源
        result = response.content
        if web_sources:
            result += "---**[行情数据来源]**"
            for i, src in enumerate(web_sources, 1):
                result += f"{i}. {src}"

        logger.info(f"行情分析完成: 查询='{query[:30]}...', 数据来源={len(web_sources)}个")
        return str(result)

    except Exception as e:
        logger.error(f"行情分析技能异常: {e}")
        return "农产品行情分析服务暂时不可用，请稍后重试。"
