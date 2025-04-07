"""Router node: classify student intent and fan out to tutor nodes."""

from langchain_core.messages import ToolMessage
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph.state import Command

from app.core.langgraph.helpers import get_last_user_content
from app.core.langgraph.models import INTENT_TO_NODE
from app.core.logging import logger
from app.schemas.graph import GraphState
from app.schemas.routing import MathIntent
from app.services.router import router_service


def make_router_node():
    """Build the async router node handler."""

    async def router(state: GraphState, config: RunnableConfig) -> Command:
        """Classify the student message and route to a specialized tutor node."""
        thread_id = config.get("configurable", {}).get("thread_id")
        user_message = get_last_user_content(state.messages)

        decision = router_service.route(user_message)
        intent = decision.intent
        reasoning = decision.reasoning

        logger.info(
            "math_intent_routed",
            session_id=thread_id,
            intent=intent.value,
            reasoning=reasoning,
        )

        intent_names = {
            MathIntent.EXPLAIN: "💡 概念精讲 (explain)",
            MathIntent.VERIFY: "✏️ 解题批改 (verify)",
            MathIntent.PRACTICE: "🎯 靶向练习 (practice)",
            MathIntent.SOLVE: "💬 综合求解 (solve)",
        }
        friendly_intent = intent_names.get(intent, intent.value)
        router_summary = (
            f"【意图分类】{friendly_intent}\n"
            f"【路由策略依据】{reasoning}"
        )
        router_msg = ToolMessage(
            content=router_summary,
            name="router_decision",
            tool_call_id=f"router_{len(state.messages)}",
        )

        goto = INTENT_TO_NODE.get(intent, "chat")
        return Command(
            update={
                "messages": [router_msg],
                "intent": intent.value,
            },
            goto=goto,
        )

    return router
