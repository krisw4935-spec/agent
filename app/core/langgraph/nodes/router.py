"""Router node: classify student intent and fan out to tutor nodes."""

from langchain_core.messages import ToolMessage
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph.state import Command

from app.core.langgraph.helpers import (
    get_last_user_content,
    get_substantive_user_content,
    is_continuation_prompt,
)
from app.core.langgraph.models import INTENT_TO_NODE
from app.core.logging import logger
from app.schemas.graph import GraphState
from app.schemas.routing import MathIntent
from app.services.router import router_service

_INTENT_FRIENDLY_NAMES: dict[MathIntent, str] = {
    MathIntent.EXPLAIN: "💡 概念精讲 (explain)",
    MathIntent.VERIFY: "✏️ 解题批改 (verify)",
    MathIntent.PRACTICE: "🎯 靶向练习 (practice)",
    MathIntent.SOLVE: "💬 综合求解 (solve)",
}


def make_router_node():
    """Build the async router node handler."""

    async def router(state: GraphState, config: RunnableConfig) -> Command:
        """Classify the student message and route to a specialized tutor node with context inheritance."""
        thread_id = config.get("configurable", {}).get("thread_id")
        user_message = get_last_user_content(state.messages)
        is_continuation = is_continuation_prompt(user_message)

        if is_continuation and state.intent in MathIntent._value2member_map_:
            intent = MathIntent(state.intent)
            friendly_intent = _INTENT_FRIENDLY_NAMES.get(intent, intent.value)
            reasoning = (
                f"【匹配方式：上下文意图继承】检测到延续/恢复指令「{user_message}」，"
                f"自动继承上一轮已规划的【{friendly_intent}】模式继续作答。"
            )
        elif is_continuation:
            substantive_message = get_substantive_user_content(state.messages)
            if substantive_message:
                decision = router_service.route(substantive_message)
                intent = decision.intent
                friendly_intent = _INTENT_FRIENDLY_NAMES.get(intent, intent.value)
                preview = (
                    (substantive_message[:30] + "...")
                    if len(substantive_message) > 30
                    else substantive_message
                )
                reasoning = (
                    f"【匹配方式：多轮上下文回溯】检测到延续/恢复指令「{user_message}」，"
                    f"自动追溯关联上轮核心问题「{preview}」，规划为【{friendly_intent}】模式。\n"
                    f"({decision.reasoning})"
                )
            else:
                decision = router_service.route(user_message)
                intent = decision.intent
                reasoning = decision.reasoning
        else:
            decision = router_service.route(user_message)
            intent = decision.intent
            reasoning = decision.reasoning

        logger.info(
            "math_intent_routed",
            session_id=thread_id,
            intent=intent.value,
            is_continuation=is_continuation,
            reasoning=reasoning,
        )

        friendly_intent = _INTENT_FRIENDLY_NAMES.get(intent, intent.value)
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

