"""Contract tests for math-tutor graph topology and routing (no Postgres required)."""

from langgraph.graph import END

from app.core.langgraph.graph_builder import GRAPH_DESTINATIONS, build_math_tutor_graph
from app.core.langgraph.models import (
    GRAPH_NODE_NAMES,
    INTENT_TO_NODE,
    TUTOR_NODE_NAMES,
    resolve_revision_target,
)
from app.core.skills import skill_registry
from app.schemas.routing import MathIntent


async def _noop_handler(*_args, **_kwargs):
    return {}


def test_intent_to_node_covers_all_math_intents():
    """Every MathIntent must map to a known tutor node."""
    assert set(INTENT_TO_NODE.keys()) == set(MathIntent)
    for node in INTENT_TO_NODE.values():
        assert node in TUTOR_NODE_NAMES


def test_resolve_revision_target_contract():
    """Critic rewrite target follows stored intent, with safe defaults."""
    assert resolve_revision_target("explain") == "explain"
    assert resolve_revision_target("verify") == "verify"
    assert resolve_revision_target("practice") == "practice"
    assert resolve_revision_target("solve") == "chat"
    assert resolve_revision_target(None) == "verify"
    assert resolve_revision_target("unknown") == "chat"


def test_graph_destinations_have_no_tool_call_node():
    """Unified in-node tool loop: graph must not declare a tool_call node."""
    assert "tool_call" not in GRAPH_DESTINATIONS
    assert "tool_call" not in GRAPH_NODE_NAMES
    for tutor in TUTOR_NODE_NAMES:
        assert GRAPH_DESTINATIONS[tutor] == ("critic",)
    assert END in GRAPH_DESTINATIONS["critic"]
    assert set(GRAPH_DESTINATIONS["router"]) == set(TUTOR_NODE_NAMES)


def test_build_math_tutor_graph_registers_expected_nodes():
    """Topology builder wires entry + destinations without finish_point."""
    handlers = {name: _noop_handler for name in GRAPH_NODE_NAMES}
    builder = build_math_tutor_graph(handlers)

    # LangGraph stores nodes on the builder; names must match contract.
    node_names = set(builder.nodes.keys()) - {"__start__", "__end__"}
    assert node_names == set(GRAPH_NODE_NAMES)

    # Termination is Command(goto=END) only — no finish_point edge declared.
    finish_points = getattr(builder, "finish_point", None)
    # StateGraph may expose finish_points as empty / unset after our builder.
    assert finish_points in (None, (), []) or not finish_points


def test_build_math_tutor_graph_requires_all_handlers():
    """Missing handlers must fail fast before compile."""
    handlers = {name: _noop_handler for name in GRAPH_NODE_NAMES if name != "critic"}
    try:
        build_math_tutor_graph(handlers)
        raise AssertionError("expected ValueError for missing critic handler")
    except ValueError as exc:
        assert "missing_graph_handlers" in str(exc)
        assert "critic" in str(exc)


def test_skill_registry_covers_all_tutor_nodes():
    """Each tutor node should have at least one registered tool for the shared loop."""
    for node in TUTOR_NODE_NAMES:
        tools = skill_registry.get_tools_for_node(node)
        assert tools, f"expected tools for tutor node {node}"


def test_skill_registry_selects_tools_by_query():
    """Only query-relevant skills should be selected for a tutor request."""
    assert skill_registry.get_skill_names_for_query("explain", "请画出二次函数的函数图像") == [
        "math_visualization"
    ]
    assert skill_registry.get_skill_names_for_query("verify", "请帮我验算这个方程") == ["algebra_calculus"]
    assert skill_registry.get_skill_names_for_query("chat", "请生成一个动画演示") == ["math_animation"]
    assert skill_registry.get_skill_names_for_query("chat", "请介绍一下学习方法") == []


def test_skill_registry_keeps_human_clarification_chat_only():
    """Human clarification is available only when chat explicitly needs a choice."""
    assert skill_registry.get_skill_names_for_query("chat", "请选择代数解法还是几何解法") == [
        "student_clarification"
    ]
    assert skill_registry.get_skill_names_for_query("explain", "请选择代数解法还是几何解法") == []
