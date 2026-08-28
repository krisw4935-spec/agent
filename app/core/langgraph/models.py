"""Shared models and routing constants for the math tutor graph."""

from pydantic import (
    BaseModel,
    Field,
)

from app.schemas.routing import MathIntent

INTENT_TO_NODE: dict[MathIntent, str] = {
    MathIntent.EXPLAIN: "explain",
    MathIntent.VERIFY: "verify",
    MathIntent.PRACTICE: "practice",
    MathIntent.SOLVE: "chat",
}

TOOL_STATUS_MESSAGES: dict[str, str] = {
    "router_decision": "🔍 正在分析题目意图与解题策略规划...",
    "python_sandbox_execute": "⚡ 正在启动 E2B 云端沙箱执行 Python 代码验证...",
    "plot_math_function": "📈 正在使用 Matplotlib 绘制函数图像与坐标系...",
    "render_math_animation": "🎞️ 正在使用 Manim 生成数学动画...",
    "sympy_calculate": "🧮 正在调用 SymPy 进行代数符号精确验算...",
    "ask_human": "🙋 正在等待用户确认与选择...",
    "critic_review": "🕵️ 正在进行 Critic 双智能体逻辑与边界质检...",
}

NODE_STATUS_MESSAGES: dict[str, str] = {
    "router": "🔍 正在分析题目意图与解题策略...",
    "explain": "💡 正在生成图文并茂概念讲解...",
    "verify": "✏️ 正在逐步批改解题步骤并核算...",
    "practice": "🎯 正在设计针对性练习题...",
    "critic": "🕵️ 正在进行 Critic 双智能体逻辑与边界质检...",
    "chat": "💬 正在组织数学辅导解答...",
}

FRIENDLY_TOOL_NAMES: dict[str, str] = {
    "router_decision": "题目意图路由与策略规划",
    "python_sandbox_execute": "Python 代码沙箱自验",
    "plot_math_function": "Matplotlib 函数图表绘制",
    "render_math_animation": "Manim 数学动画生成",
    "sympy_calculate": "SymPy 代数精确核算",
    "ask_human": "等待用户确认与选择",
    "critic_review": "Critic 双智能体审校与质检",
}

TUTOR_NODE_NAMES: tuple[str, ...] = ("explain", "verify", "practice", "chat")
GRAPH_NODE_NAMES: tuple[str, ...] = ("router", *TUTOR_NODE_NAMES, "critic")


class CriticDecision(BaseModel):
    """Structured evaluation returned by the Critic reviewer node."""

    is_approved: bool = Field(
        default=True,
        description="Whether the response is mathematically sound, boundary-safe, and pedagogically helpful",
    )
    reasoning: str = Field(
        default="",
        description="Detailed step-by-step thinking process and evaluation analysis across the 6 criteria",
    )
    feedback: str = Field(
        default="",
        description="Constructive and specific feedback for revision if rejected",
    )
    score: int = Field(
        default=8,
        description="Quality score from 1 to 10",
    )


def resolve_revision_target(intent: str | None) -> str:
    """Map stored intent back to the tutor node that should rewrite after critic rejection."""
    if not intent:
        return "verify"
    try:
        intent_enum = MathIntent(intent)
        return INTENT_TO_NODE.get(intent_enum, "chat")
    except ValueError:
        return "chat"
