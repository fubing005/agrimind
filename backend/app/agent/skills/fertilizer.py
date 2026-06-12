"""精准施肥决策技能 (fertilizer_calc)

根据作物品种、生长周期、土壤检测数据，计算出氮磷钾配比方案。
"""
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage

from app.core.config import settings
from pydantic import SecretStr

logger = logging.getLogger(__name__)

FERTILIZER_CALC_SYSTEM_PROMPT = """你是「农知睿策」的精准施肥决策专家。你的职责是根据用户提供的作物信息和土壤数据，计算出科学的氮磷钾配比施肥方案。

施肥决策流程：
1. **信息收集**：确认作物品种、生长阶段、种植面积、土壤类型和检测结果。
2. **需肥分析**：根据作物需肥规律，分析当前阶段的氮(N)、磷(P₂O₅)、钾(K₂O)需求量。
3. **配方计算**：结合土壤养分含量，计算推荐施肥量（kg/亩）。
4. **施肥方案**：给出基肥、追肥的施用时间和方法。

输出格式要求（必须严格遵守）：
## 🌾 作物需肥分析
- **作物品种**：xxx
- **生长阶段**：xxx
- **目标产量**：xxx kg/亩

## 📊 推荐施肥配方
| 养分 | 推荐用量(kg/亩) | 说明 |
|------|-----------------|------|
| 氮(N) | xxx | xxx |
| 磷(P₂O₅) | xxx | xxx |
| 钾(K₂O) | xxx | xxx |

## 📅 施肥时间表
1. **基肥**（时间）：xxx，施用方法：xxx
2. **追肥1**（时间）：xxx，施用方法：xxx
3. **追肥2**（时间）：xxx，施用方法：xxx

## 💡 推荐肥料产品
- xxx复合肥（N-P-K=xx-xx-xx），用量：xxx kg/亩

## ⚠️ 注意事项
- xxx

如果用户未提供足够信息，请列出需要补充的关键数据（如：土壤pH值、有机质含量、前茬作物等），并给出一个基于常规情况的参考方案。"""

# 施肥相关关键词
FERTILIZER_KEYWORDS = [
    "施肥", "肥料", "氮", "磷", "钾", "NPK", "npk", "复合肥", "尿素",
    "追肥", "基肥", "底肥", "有机肥", "化肥", "叶面肥", "配方肥",
    "土壤", "肥力", "缺肥", "烧苗", "肥害", "测土", "配比",
    "磷酸二铵", "氯化钾", "硫酸钾", "过磷酸钙", "碳酸氢铵",
    "fertilizer", "nutrient", "nitrogen", "phosphorus", "potassium",
]


def is_fertilizer_related(query: str) -> bool:
    """判断用户问题是否与施肥决策相关

    Args:
        query: 用户查询文本

    Returns:
        是否与施肥相关
    """
    query_lower = query.lower()
    return any(kw in query_lower for kw in FERTILIZER_KEYWORDS)


async def fertilizer_calc_skill(
    query: str,
    local_context: str = "",
    web_context: str = "",
) -> str:
    """精准施肥决策技能

    Args:
        query: 用户查询文本
        local_context: 本地知识库检索上下文
        web_context: 联网搜索上下文

    Returns:
        施肥方案文本
    """
    try:
        llm = ChatOpenAI(
            api_key=SecretStr(settings.OPENAI_API_KEY),
            base_url=settings.OPENAI_BASE_URL,
            model=settings.OPENAI_MODEL,
            temperature=0.2,
        )

        messages: list[BaseMessage] = [SystemMessage(content=FERTILIZER_CALC_SYSTEM_PROMPT)]


        # 添加参考上下文
        context_parts = []
        if local_context:
            context_parts.append(f"【本地知识库参考资料】{local_context}")
        if web_context:
            context_parts.append(f"【联网搜索参考资料】{web_context}")

        user_message = query
        if context_parts:
            user_message += "" + "".join(context_parts)

        messages.append(HumanMessage(content=user_message))

        response = await llm.ainvoke(messages)
        logger.info(f"施肥决策完成: 查询='{query[:30]}...'")
        return str(response.content)

    except Exception as e:
        logger.error(f"施肥决策技能异常: {e}")
        return "施肥决策服务暂时不可用，请稍后重试。"
