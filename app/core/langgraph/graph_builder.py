"""Pure graph topology wiring — testable without Postgres checkpointer."""

from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.graph.state import Command

from app.core.langgraph.models import GRAPH_NODE_NAMES, TUTOR_NODE_NAMES
from app.schemas.graph import GraphState

NodeHandler = Callable[..., Awaitable[Command | dict[str, Any]]]

# Declared destinations used by both compile-time wiring and contract tests.
GRAPH_DESTINATIONS: dict[str, tuple[str, ...]] = {
    "router": TUTOR_NODE_NAMES,
    "explain": ("critic",),
    "verify": ("critic",),
    "practice": ("critic",),
    "chat": ("critic",),
    "critic": (*TUTOR_NODE_NAMES, END),
}


def build_math_tutor_graph(handlers: dict[str, NodeHandler]) -> StateGraph:
    """Register math-tutor nodes on a StateGraph.

    Termination is expressed only via ``Command(goto=END)`` from critic —
    no ``set_finish_point``, so rewrite loops remain explicit.
    """
    missing = [name for name in GRAPH_NODE_NAMES if name not in handlers]
    if missing:
        raise ValueError(f"missing_graph_handlers: {missing}")

    graph_builder = StateGraph(GraphState)
    graph_builder.add_node(
        "router",
        handlers["router"],
        destinations=GRAPH_DESTINATIONS["router"],
    )
    for tutor in TUTOR_NODE_NAMES:
        graph_builder.add_node(
            tutor,
            handlers[tutor],
            destinations=GRAPH_DESTINATIONS[tutor],
        )
    graph_builder.add_node(
        "critic",
        handlers["critic"],
        destinations=GRAPH_DESTINATIONS["critic"],
    )
    graph_builder.set_entry_point("router")
    return graph_builder
