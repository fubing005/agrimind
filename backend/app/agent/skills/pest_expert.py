"""病虫害智能诊断技能 (pest_expert)

根据植物病征描述，匹配病因并给出生物/化学防治方案。
"""
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage

from app.core.config import settings
from pydantic import SecretStr

logger = logging.getLogger(__name__)

PEST_EXPERT_SYSTEM_PROMPT = """你是「农知睿策」的病虫害智能诊断专家。你的职责是根据用户描述的植物病征，进行专业诊断并给出防治方案。

诊断流程：
1. **症状分析**：根据用户描述的病征（叶片斑点、枯萎、虫洞、变色等），初步判断病害或虫害类型。
2. **病因匹配**：结合作物种类、生长阶段、环境条件，匹配最可能的病因。
3. **防治方案**：给出生物防治和化学防治两种方案，优先推荐绿色防控。

输出格式要求（必须严格遵守）：
## 🦠 诊断结果
- **病害/虫害名称**：xxx
- **置信度**：高/中/低
- **致病原因**：xxx

## 🌿 生物防治方案
1. xxx
2. xxx

## 🧪 化学防治方案
1. xxx（药剂名称、稀释倍数、施用方法）
2. xxx

## ⚠️ 注意事项
- xxx

如果信息不足以做出准确诊断，请明确告知用户需要补充哪些信息（如：作物品种、病征照片、发生环境等）。"""

# 病虫害相关关键词（用于技能路由判断）
PEST_KEYWORDS = [
    "病虫害", "虫害", "病害", "虫子", "飞虱", "蚜虫", "螟虫", "蚧壳虫",
    "锈病", "枯萎病", "白粉病", "稻瘟病", "灰霉病", "霜霉病", "炭疽病",
    "斑点", "枯萎", "黄化", "卷叶", "虫洞", "蛀虫", "地老虎", "线虫",
    "病征", "病状", "诊断", "防治", "杀虫", "杀菌", "农药", "喷药",
    "pest", "disease", "insect", "blight", "rot", "mold", "wilt",
]


def is_pest_related(query: str) -> bool:
    """判断用户问题是否与病虫害诊断相关

    Args:
        query: 用户查询文本

    Returns:
        是否与病虫害相关
    """
    query_lower = query.lower()
    return any(kw in query_lower for kw in PEST_KEYWORDS)


async def pest_expert_skill(
    query: str,
    local_context: str = "",
    web_context: str = "",
) -> str:
    """病虫害智能诊断技能

    Args:
        query: 用户查询文本
        local_context: 本地知识库检索上下文
        web_context: 联网搜索上下文

    Returns:
        诊断结果文本
    """
    try:
        llm = ChatOpenAI(
            api_key=SecretStr(settings.OPENAI_API_KEY),
            base_url=settings.OPENAI_BASE_URL,
            model=settings.OPENAI_MODEL,
            temperature=0.2,
        )

        # 构建消息
        messages: list[BaseMessage] = [SystemMessage(content=PEST_EXPERT_SYSTEM_PROMPT)]

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
        logger.info(f"病虫害诊断完成: 查询='{query[:30]}...'")
        return str(response.content)

    except Exception as e:
        logger.error(f"病虫害诊断技能异常: {e}")
        return "病虫害诊断服务暂时不可用，请稍后重试。"
