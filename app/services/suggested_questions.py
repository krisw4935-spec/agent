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

INSPIRATION_POOL: List[str] = [
    "校园生活：设计一份班级春游路线，比较步行、公交和骑行的时间与费用",
    "家庭消费：研究外卖满减、优惠券和配送费叠加后的最划算点单方案",
    "运动竞技：用投篮命中率、跑步配速或足球射门数据比较选手表现",
    "游戏策略：分析掷骰子、抽卡、猜数字或抢数游戏背后的获胜策略",
    "自然观察：从树叶、蜂巢、花瓣、雪花或贝壳中寻找图形和数量规律",
    "建筑设计：为窗户、拱门、楼梯或屋顶设计尺寸并估算材料用量",
    "城市出行：根据地铁换乘、出租车计费或共享单车规则进行路线规划",
    "食谱实验：按人数、比例和损耗调整饮料、蛋糕或果汁的配方",
    "时间规律：研究钟表指针重合、日期循环、作息安排或倒计时中的规律",
    "空间想象：用纸张、积木、魔方或包装盒探索展开图、体积和最短路线",
    "视觉错觉：解释透视、镜面反射、旋转对称或看起来“不一样”的图形",
    "测量挑战：不用直接攀爬，估算旗杆、大树、楼房或河宽的实际尺寸",
    "数据侦探：从一张成绩、天气、步数或消费表中发现平均数之外的结论",
    "工程优化：设计纸桥、纸盒、储水桶或围栏，让材料少但承载或容量更大",
    "历史密码：用古人计数法、密码表、地图比例尺或历法讲一个数学故事",
    "艺术创作：用分形、镶嵌、黄金分割或对称图案制作一幅数学画",
    "反直觉现象：探究零、负数、无穷小数、概率或面积中一个容易误判的问题",
    "经典趣题：从鸡兔同笼、假币、过河、切披萨或猴子分桃改编出新挑战",
    "数字世界：解释二维码、验证码、二进制、像素或压缩中隐藏的数学",
    "环保规划：估算家庭用水用电、垃圾分类或太阳能板的数量与节约效果",
    "商业模拟：为奶茶店、文具店或游乐园制定定价、排队和库存方案",
    "体育场馆：研究跑道、看台、球场边界或摩天轮运动中的角度和距离",
    "天气与科学：用温度变化、降雨概率或日影长度建立一个简单数学模型",
    "自由创作：把一个熟悉物品改造成同时包含代数、几何或概率问题的谜题",
]

QUESTION_STYLES: List[str] = [
    "让学生先猜结果，再用数学验证直觉是否正确",
    "设计成可以动手画图、折纸、测量或在纸上模拟的小实验",
    "从一个真实选择出发，比较至少两种方案并说明如何优化",
    "设置一个有趣的反例或错误解法，请导师带着找出错在哪里",
    "设计成逐步升级的挑战，先解决基础问题，再追问一个变化情形",
    "采用‘如果……会怎样’的假设，引导观察规律并归纳结论",
    "让学生自己提出猜想，再给出适合其学段的证明或解释路线",
    "把数学知识和体育、艺术、科技、自然或历史中的一个元素连接起来",
    "设计一个适合两人或小组玩的数学游戏，并追问怎样制定必胜策略",
    "从一张表格、图像或一组数据出发，要求解读而不是只计算答案",
    "把题目改写成侦探故事，让关键数字或条件成为破案线索",
    "鼓励用两种不同方法解决同一个问题，并比较它们的优缺点",
]


def _pick_random_inspirations() -> List[str]:
    """Sample unrelated themes so each greeting can explore a different mix of ideas."""
    return random.sample(INSPIRATION_POOL, k=4)


def _build_user_prompt(inspirations: List[str]) -> str:
    """Build a diversity-focused generation prompt from a random set of themes."""
    styles = random.sample(QUESTION_STYLES, k=4)
    creative_cards = "\n".join(
        f"{index}. 主题方向：{inspiration}\n   建议切入方式：{style}"
        for index, (inspiration, style) in enumerate(zip(inspirations, styles, strict=True), start=1)
    )
    return (
        "请从下面 4 个随机创意卡片中自由取材，生成恰好 4 个适合新对话的数学推荐问题。"
        "每张卡片只是灵感，不要照抄，也不要把四题机械写成同一种题型：\n"
        f"{creative_cards}\n\n"
        "本轮最重要的目标是发散：四个问题应尽量在主题场景、数学分支、提问方式和情绪体验上拉开差异。"
        "不要求固定覆盖小学、初中、高中、综合四种维度，学段可以自然混合；但每题的 grade 必须和实际难度一致。"
        "本轮避免优先生成鸡兔同笼、摩天轮、披萨切块、房贷或单纯解方程等套路，除非对它们做出明显新颖的改编。"
        "问题必须生动具体、学生一看就想点击，并且可以直接作为发给数学导师的完整提问。"
    )


async def generate_suggested_questions(
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> list[SuggestedQuestion]:
    """Generate diverse starter questions via LLM while keeping each question within K-12."""
    inspirations = _pick_random_inspirations()
    user_prompt = _build_user_prompt(inspirations)

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
