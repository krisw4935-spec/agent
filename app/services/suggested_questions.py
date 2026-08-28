"""Generate AI suggested starter questions for new chat greetings."""

from contextlib import nullcontext
import random
from typing import List, Optional

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.core.config import settings
from app.core.logging import logger
from app.core.observability import langfuse_callback_handler, langfuse_trace_context
from app.core.prompts import SUGGESTED_QUESTIONS_PROMPT
from app.schemas.chat import SuggestedQuestion, SuggestedQuestionsResult
from app.services.llm import llm_service

INSPIRATION_POOLS: List[List[str]] = [
    # 维度1：小学数学趣味与基础思维（1-6年级）
    [
        "小学趣味思维：经典鸡兔同笼问题的假设置换法与直观画图法",
        "小学应用题：相遇追及行程问题与时钟分针时针重合规律",
        "小学平面几何：剪纸拼图与长方形/正方形周长面积巧算",
        "小学数感规律：高斯速算等差数列求和 1+2+...+100 及其生活巧算",
        "小学生活数学：买几赠几打折优惠与购物最省钱方案",
        "小学图形割补：用割补法巧算阴影部分面积与圆的周长认识",
    ],
    # 维度2：初中数学代数与几何进阶（7-9年级）
    [
        "初中勾股定理：用勾股定理测量建筑物高度与生活斜坡距离",
        "初中一次函数：手机套餐选择/出租车计费的分段函数与最优化方案",
        "初中平面几何：相似三角形在阳光投影测树高中的实际应用",
        "初中方程与不等式：二元一次方程组在浓度配比与配料问题中的应用",
        "初中反比例函数：物理杠杆平衡原理与双杠受力关系图示",
        "初中概率统计：商场幸运大转盘与中奖概率的统计学揭秘",
    ],
    # 维度3：高中数学函数与空间探究（10-12年级）
    [
        "高中三角函数：摩天轮座舱高度随时间变化的正弦周期函数建模与图像绘制",
        "高中二次函数与导数：投篮抛物线运动轨迹与最高点/最大射程极值问题",
        "高中数列与金融：等比数列求和在房贷等额本息还款模型中的计算",
        "高中立体几何：长方体与圆柱体在包装盒体积最大化设计中的空间几何探究",
        "高中解析几何：汽车大灯与卫星天线抛物面镜的光学聚焦特性",
        "高中排列组合：高考选科组合方式与彩票中奖概率的计数原理",
    ],
    # 维度4：综合生活建模与直觉挑战（中小学通用趣味）
    [
        "生活趣味建模：切一个圆形披萨，切 n 刀最多能分出多少块（割圆数列规律）",
        "直觉思维挑战：天平称重用最少次数找出轻质假币（三分法思维）",
        "反直觉找茬：无限循环小数 0.999... 为什么严格等于 1 的直观推导",
        "自然数学之美：向日葵花盘与斐波那契数列螺旋对称之谜",
        "趣味几何拓扑：一张纸条剪一刀为什么变成一个大环（莫比乌斯带的奇妙探索）",
        "生活博弈策略：抢20游戏与必胜倒推策略（同余与余数周期）",
    ],
]


def _pick_random_inspirations() -> List[str]:
    """Sample one inspiration theme from each of the 4 grade dimensions (小学, 初中, 高中, 综合生活)."""
    return [random.choice(pool) for pool in INSPIRATION_POOLS]


async def generate_suggested_questions(
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> list[SuggestedQuestion]:
    """Generate starter questions via LLM with Langfuse tracing across Elementary, Middle, and High school dimensions."""
    inspirations = _pick_random_inspirations()
    theme_bullet_points = "\n".join(f"{i + 1}. {item}" for i, item in enumerate(inspirations))
    user_prompt = (
        f"请基于以下 4 个涵盖小学、初中、高中及生活趣味维度的灵感，分别构思 4 个极具吸引力、符合中小学认知难度的推荐问题：\n"
        f"{theme_bullet_points}\n\n"
        "请确保生成的推荐问题难度严格适配中小学（小学、初中、高中）知识体系，拒绝大学超纲难题，问题生动具体、可直接点击发送。"
    )

    callbacks: list[BaseCallbackHandler] = [langfuse_callback_handler] if settings.LANGFUSE_TRACING_ENABLED else []
    run_config: RunnableConfig = {
        "callbacks": callbacks,
        "run_name": "generate_suggested_questions",
        "tags": ["suggested-questions", "greeting"],
        "metadata": {
            "langfuse_session_id": session_id or "anonymous",
            "langfuse_user_id": user_id or "anonymous",
            "environment": settings.ENVIRONMENT.value,
        },
    }

    trace_ctx = langfuse_trace_context(session_id, user_id) if session_id else nullcontext()
    with trace_ctx:
        result = await llm_service.call(
            [
                SystemMessage(content=SUGGESTED_QUESTIONS_PROMPT),
                HumanMessage(content=user_prompt),
            ],
            response_format=SuggestedQuestionsResult,
            config=run_config,
            max_tokens=1024,
            temperature=0.95,
            extra_body={"thinking": {"type": "disabled"}},
        )
    questions = list(result.questions)[:4]
    logger.info(
        "suggested_questions_generated",
        session_id=session_id,
        user_id=user_id,
        count=len(questions),
        inspirations=inspirations,
    )
    return questions
