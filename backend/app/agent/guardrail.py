"""农业边界拦截器 — 非农业问题前置分类拦截"""
import json
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage

from app.core.config import settings
from app.schemas.chat import GuardrailResult
from app.agent.state import AgentState
from pydantic import SecretStr

logger = logging.getLogger(__name__)

# 边界拦截系统提示词
GUARDRAIL_SYSTEM_PROMPT = """你是一个专业的农业领域分类器。你的任务是判断用户的问题是否与农业相关。

农业相关领域包括但不限于：
- 作物种植（水稻、小麦、玉米、大豆、蔬菜、水果等）
- 病虫害防治（诊断、生物防治、化学防治）
- 土壤肥力（土壤检测、改良、施肥方案）
- 农机具使用（操作、维护、选型）
- 农产品市场行情（价格、供需、趋势）
- 农业政策与补贴
- 畜牧养殖
- 水产养殖
- 林业与园艺
- 农业气象与灾害应对

非农业领域包括但不限于：
- IT编程、软件开发
- 娱乐八卦、明星新闻
- 通用哲学、宗教讨论
- 医学健康（非兽医）
- 金融投资（非农产品）
- 政治、军事
- 旅游、美食（非农业种植）

请严格按照以下 JSON 格式输出，不要输出任何其他内容：
{
    "is_agriculture": true/false,
    "confidence": 0.0-1.0,
    "category": "农业子类别或null",
    "reason": "分类理由"
}"""

GUARDRAIL_BLOCKED_MESSAGE = "我是农知睿策，我只能为您提供专业的农业相关知识解答。"


async def guardrail_node(state: AgentState) -> dict:
    """边界拦截器节点

    对用户输入进行语义分类，判断是否属于农业领域。
    非农业问题将被拦截，直接返回固定拒绝语。

    Args:
        state: 当前智能体状态

    Returns:
        状态更新字典
    """
    user_input = state.user_input

    # 快速关键词预检：包含明显农业关键词的直接放行
    agriculture_keywords = [
        "种植", "养殖", "施肥", "病虫害", "农药", "种子", "收割",
        "灌溉", "土壤", "作物", "水稻", "小麦", "玉米", "大豆",
        "蔬菜", "水果", "畜牧", "水产", "农机", "农产品", "行情",
        "农药", "化肥", "有机肥", "大棚", "温室", "旱涝", "干旱",
        "丰收", "播种", "育苗", "嫁接", "除草", "松土", "追肥",
        "稻飞虱", "蚜虫", "锈病", "枯萎病", "农业", "农民", "耕地",
        "crop", "farm", "pest", "fertilizer", "harvest", "irrigation",
        "soil", "livestock", "aquaculture", "agriculture",
    ]

    user_input_lower = user_input.lower()
    quick_match = any(kw in user_input_lower for kw in agriculture_keywords)

    if quick_match:
        logger.info(f"边界拦截器[快速放行]: '{user_input[:50]}...'")
        return {
            "guardrail_result": GuardrailResult(
                is_agriculture=True,
                confidence=0.95,
                category="农业（关键词快速匹配）",
                reason="用户输入包含明确的农业领域关键词",
            ),
            "blocked": False,
        }

    # LLM 语义分类
    try:
        llm = ChatOpenAI(
            api_key=SecretStr(settings.OPENAI_API_KEY),
            base_url=settings.OPENAI_BASE_URL,
            model=settings.OPENAI_MODEL,
            temperature=settings.GUARDRAIL_TEMPERATURE,
            max_retries=settings.GUARDRAIL_MAX_RETRIES,
        )

        response = await llm.ainvoke([
            SystemMessage(content=GUARDRAIL_SYSTEM_PROMPT),
            HumanMessage(content=f"请判断以下问题是否与农业相关：{user_input}"),
        ])

        # 解析 LLM 返回的 JSON
        result = _parse_guardrail_response(str(response.content))
        logger.info(
            f"边界拦截器[LLM分类]: is_agriculture={result.is_agriculture}, "
            f"confidence={result.confidence}, category={result.category}"
        )

        return {
            "guardrail_result": result,
            "blocked": not result.is_agriculture,
        }

    except Exception as e:
        logger.error(f"边界拦截器异常: {e}")
        # 异常时保守放行，避免误拦截
        return {
            "guardrail_result": GuardrailResult(
                is_agriculture=True,
                confidence=0.5,
                category=None,
                reason=f"拦截器异常，保守放行: {str(e)}",
            ),
            "blocked": False,
        }


def _parse_guardrail_response(content: str) -> GuardrailResult:
    """解析 LLM 返回的 JSON 格式拦截结果

    Args:
        content: LLM 返回的文本内容

    Returns:
        GuardrailResult 拦截结果
    """
    try:
        # 尝试提取 JSON（处理 LLM 可能输出的额外文本）
        json_str = content.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()

        data = json.loads(json_str)
        return GuardrailResult(
            is_agriculture=bool(data.get("is_agriculture", False)),
            confidence=float(data.get("confidence", 0.0)),
            category=data.get("category"),
            reason=data.get("reason"),
        )
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning(f"解析拦截器响应失败: {e}, 原始内容: {content}")
        # 解析失败时保守放行
        return GuardrailResult(
            is_agriculture=True,
            confidence=0.5,
            category=None,
            reason=f"解析失败，保守放行",
        )
