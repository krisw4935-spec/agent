"""Tests for router decision details, critic reasoning, and 429 error handling."""

from langchain_core.messages import AIMessage

from app.core.langgraph.graph import (
    CriticDecision,
    _degrade_tutor_tool_loop,
    _get_friendly_tool_name,
    _is_rate_limit_error,
)
from app.core.langgraph.helpers import (
    degrade_tutor_tool_loop,
    get_friendly_tool_name,
    is_rate_limit_error,
)
from app.schemas.routing import MathIntent, RouterDecision


def test_critic_decision_schema():
    """Verify CriticDecision captures reasoning, score, feedback, and approval."""
    decision = CriticDecision(
        is_approved=True,
        reasoning="1. 代数计算准确；2. 边界条件完备；3. 启发式教学引导清晰。",
        feedback="",
        score=9,
    )
    assert decision.is_approved is True
    assert "代数计算准确" in decision.reasoning
    assert decision.score == 9


def test_friendly_tool_names():
    """Verify friendly tool name mapping for router and critic."""
    assert _get_friendly_tool_name("router_decision") == "题目意图路由与策略规划"
    assert _get_friendly_tool_name("critic_review") == "Critic 双智能体审校与质检"
    assert _get_friendly_tool_name("python_sandbox_execute") == "Python 代码沙箱自验"
    assert get_friendly_tool_name("router_decision") == _get_friendly_tool_name("router_decision")


def test_is_rate_limit_error():
    """Verify detection of 429 and rate limit exception messages."""
    e1 = RuntimeError("Error 429: TPM exhausted for model")
    e2 = Exception("Rate limit exceeded. Please wait.")
    e3 = ValueError("Regular syntax error")

    assert _is_rate_limit_error(e1) is True
    assert _is_rate_limit_error(e2) is True
    assert _is_rate_limit_error(e3) is False
    assert is_rate_limit_error(e1) is _is_rate_limit_error(e1)


def test_degrade_tutor_tool_loop_with_429():
    """Verify degradation message structure on 429 error."""
    err = RuntimeError("429 Too Many Requests: TPM limit reached")
    partial_messages = [AIMessage(content="首先设未知数 x，根据题目条件列出方程。")]

    degraded = _degrade_tutor_tool_loop(partial_messages, err)
    assert "429 速率限制" in str(degraded.content)
    assert "已完成的推导与验算结果" in str(degraded.content)
    assert "首先设未知数 x" in str(degraded.content)
    assert degrade_tutor_tool_loop(partial_messages, err).content == degraded.content



def test_router_decision_schema():
    """Verify RouterDecision schema supports intent and reasoning."""
    decision = RouterDecision(
        intent=MathIntent.EXPLAIN,
        reasoning="学生提问概念含义，无需直接批改作业。",
    )
    assert decision.intent == MathIntent.EXPLAIN
    assert "学生提问概念含义" in decision.reasoning


def test_hierarchical_hybrid_router_explicit_prefixes():
    """Verify explicit prefixes route correctly and immediately."""
    from app.services.router import router_service

    d1 = router_service.route("[verify] 这是我的解法：x^2=4 得 x=2")
    assert d1.intent == MathIntent.VERIFY
    assert "显式意图指令" in d1.reasoning

    d2 = router_service.route("【概念讲解】请问什么是矩阵的秩？")
    assert d2.intent == MathIntent.EXPLAIN
    assert "显式意图指令" in d2.reasoning

    d3 = router_service.route("/practice 给我来两道立体几何题目")
    assert d3.intent == MathIntent.PRACTICE
    assert "显式意图指令" in d3.reasoning


def test_hierarchical_hybrid_router_rules():
    """Verify heuristic feature rules classify properly."""
    from app.services.router import router_service

    # Verify rule
    dv = router_service.route("老师帮我批改一下这道题算得对不对，第2步是否有错")
    assert dv.intent == MathIntent.VERIFY

    # Practice rule
    dp = router_service.route("针对导数知识点，再给我出几道测试题考考我")
    assert dp.intent == MathIntent.PRACTICE

    # Explain rule
    de = router_service.route("什么是泰勒展开公式，它的几何意义是什么？")
    assert de.intent == MathIntent.EXPLAIN

    # Solve rule
    ds = router_service.route("已知函数 f(x) = x^3 - 3x + 1，求解函数的单调递增区间")
    assert ds.intent == MathIntent.SOLVE


def test_hierarchical_hybrid_router_fallback():
    """Verify empty or ambiguous messages gracefully fallback to solve mode."""
    from app.services.router import router_service

    d_empty = router_service.route("")
    assert d_empty.intent == MathIntent.SOLVE

    d_ambiguous = router_service.route("你好呀今天天气真不错")
    assert d_ambiguous.intent == MathIntent.SOLVE


def test_structured_output_method_default():
    """Verify that STRUCTURED_OUTPUT_METHOD defaults to function_calling to prevent xgrammar errors."""
    from app.core.config import settings

    assert hasattr(settings, "STRUCTURED_OUTPUT_METHOD")
    assert settings.STRUCTURED_OUTPUT_METHOD in ("function_calling", "json_schema", "json_mode")

