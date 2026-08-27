"""Unit tests for context-aware routing, intent inheritance, and continuation prompt detection."""

import asyncio
from langchain_core.messages import AIMessage, HumanMessage

from app.core.langgraph.helpers import (
    format_context_aware_input,
    get_substantive_user_content,
    is_continuation_prompt,
)
from app.core.langgraph.nodes.router import make_router_node
from app.schemas.graph import GraphState


def test_is_continuation_prompt():
    """Verify various continuation prompt variants are accurately detected."""
    assert is_continuation_prompt("") is True
    assert is_continuation_prompt("请继续") is True
    assert is_continuation_prompt("继续") is True
    assert is_continuation_prompt("请接着讲。") is True
    assert is_continuation_prompt("接着推导") is True
    assert is_continuation_prompt("【继续生成请求】请继续") is True
    assert is_continuation_prompt("请紧接着上一轮的推导和内容继续回答。") is True

    # Substantive questions should NOT be detected as continuation
    assert is_continuation_prompt("贷款100万、年利率4%、分30年还，每月月供到底是怎么推导出来的？") is False
    assert is_continuation_prompt("帮我批改一下这道导数题对不对") is False
    assert is_continuation_prompt("已知函数 f(x) = x^2，求导数") is False


def test_get_substantive_user_content():
    """Verify backtracking through history retrieves the original substantive question."""
    history = [
        HumanMessage(content="我爸妈在讨论等额本息房贷，能不能用等比数列求和公式帮我推导一下？"),
        AIMessage(content="好的，我们先列出每月还款和利息的模型..."),
        HumanMessage(content="请继续"),
        AIMessage(content="接下来计算第n个月的本金..."),
        HumanMessage(content="【继续生成请求】继续"),
    ]
    substantive = get_substantive_user_content(history)
    assert "我爸妈在讨论等额本息房贷" in substantive


def test_format_context_aware_input():
    """Verify context-aware input formatting for UI visibility."""
    substantive = "贷款100万、年利率4%、分30年还，月供推导"
    formatted = format_context_aware_input("请继续", substantive)
    assert "请继续" in formatted
    assert "关联上轮主题与上下文" in formatted
    assert substantive in formatted

    # Normal question remains unmodified
    normal = "什么是泰勒展开？"
    assert format_context_aware_input(normal, normal) == normal


def test_router_node_intent_inheritance():
    """Verify that when state.intent exists, continuation prompts inherit it."""
    async def _run():
        router_fn = make_router_node()
        state = GraphState(
            intent="explain",
            messages=[
                HumanMessage(content="能带我用等比数列求和公式推导等额本息月供吗？"),
                AIMessage(content="好的，我们设贷款总额为 P..."),
                HumanMessage(content="请继续"),
            ],
        )
        config = {"configurable": {"thread_id": "test-session-001"}}

        command = await router_fn(state, config)
        assert command.goto == "explain"
        assert command.update["intent"] == "explain"

        tool_msg = command.update["messages"][0]
        assert "上下文意图继承" in tool_msg.content
        assert "概念精讲 (explain)" in tool_msg.content

    asyncio.run(_run())


def test_router_node_context_retrospective_routing():
    """Verify that when state.intent is empty, continuation prompts retrospectively route against original question."""
    async def _run():
        router_fn = make_router_node()
        state = GraphState(
            intent="",  # empty initially
            messages=[
                HumanMessage(content="什么是等比数列求和公式？为什么推导中公比不能为1？"),
                AIMessage(content="等比数列求和公式的推导采用错位相减法..."),
                HumanMessage(content="请继续"),
            ],
        )
        config = {"configurable": {"thread_id": "test-session-002"}}

        command = await router_fn(state, config)
        assert command.goto == "explain"
        assert command.update["intent"] == "explain"

        tool_msg = command.update["messages"][0]
        assert "多轮上下文回溯" in tool_msg.content
        assert "什么是等比数列求和公式" in tool_msg.content

    asyncio.run(_run())


def test_router_node_regular_routing():
    """Verify that regular new questions route normally."""
    async def _run():
        router_fn = make_router_node()
        state = GraphState(
            intent="",
            messages=[
                HumanMessage(content="这是我做的证明步骤，请老师帮我批改一下对不对"),
            ],
        )
        config = {"configurable": {"thread_id": "test-session-003"}}

        command = await router_fn(state, config)
        assert command.goto == "verify"
        assert command.update["intent"] == "verify"

    asyncio.run(_run())
