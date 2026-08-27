"""Unified in-node tool-loop tutors (explain / verify / practice / chat).

All tutoring modes share one ReAct-style loop. There is no separate graph-level
``tool_call`` node — tool rounds stay inside the tutor node, then route to critic.
"""

from typing import (
    Any,
    Awaitable,
    Callable,
)

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    ToolMessage,
)
from langchain_core.runnables.config import RunnableConfig
from langchain_core.tools.base import BaseTool
from langgraph.errors import GraphInterrupt
from langgraph.graph.state import Command

from app.core.config import settings
from app.core.langgraph.helpers import (
    degrade_tutor_tool_loop,
    is_rate_limit_error,
    normalize_messages,
)
from app.core.logging import logger
from app.core.metrics import llm_inference_duration_seconds
from app.core.prompts import load_node_prompt, load_system_prompt
from app.core.skills import skill_registry
from app.schemas.graph import GraphState
from app.services.llm import llm_service
from app.utils import (
    dump_messages,
    extract_text_content,
    prepare_messages,
    process_llm_response,
)

TutorHandler = Callable[[GraphState, RunnableConfig], Awaitable[Command]]

_DEFAULT_MAX_TOOL_ROUNDS: dict[str, int] = {
    "explain": 3,
    "verify": 4,
    "practice": 3,
    "chat": 3,
}


def _build_tutor_prompt(node: str, state: GraphState, username: str | None) -> str:
    """Build the system prompt for a tutor node, including skills and critic feedback."""
    if node == "chat":
        prompt = load_system_prompt(
            username=username,
            long_term_memory=state.long_term_memory,
            evolved_lessons=state.evolved_lessons,
        )
        skill_guide = skill_registry.get_prompt_guide_for_node("chat")
        if skill_guide:
            prompt += f"\n\n## 推荐调用的专业数学技能 (Registered Skills)\n{skill_guide}\n"
        if state.review_feedback:
            prompt += (
                f"\n\n## 审校专家修改意见 (请务必针对性修正)\n"
                f"上一轮回答未通过质检审校，请认真修正后重新作答：\n{state.review_feedback}\n"
            )
        return prompt

    return load_node_prompt(
        node,
        username=username,
        long_term_memory=state.long_term_memory,
        review_feedback=state.review_feedback,
        evolved_lessons=state.evolved_lessons,
    )


async def run_tutor_with_tools(
    state: GraphState,
    config: RunnableConfig,
    node: str,
    tutor_tools: list[BaseTool],
    max_tool_rounds: int = 3,
) -> Command:
    """Run a tutoring node with an internal tool loop, then hand off to critic.

    Uses llm_service retries/fallback. On rate-limit mid-loop, degrades to a
    partial reply built from completed LLM text + tool results.
    """
    thread_id = config.get("configurable", {}).get("thread_id")
    username = config.get("metadata", {}).get("username")
    model_name = settings.DEFAULT_LLM_MODEL

    system_prompt = _build_tutor_prompt(node, state, username)
    conversation: list[Any] = dump_messages(
        prepare_messages(normalize_messages(state.messages), system_prompt)
    )
    tools_by_name = {tool.name: tool for tool in tutor_tools}
    new_messages: list[BaseMessage] = []

    try:
        for round_idx in range(max_tool_rounds):
            with llm_inference_duration_seconds.labels(model=model_name).time():
                response_message = await llm_service.call(
                    conversation,
                    tools=tutor_tools if tutor_tools else None,
                    config=config,
                )
            if not isinstance(response_message, BaseMessage):
                raise TypeError("expected BaseMessage from llm_service.call")
            response_message = process_llm_response(response_message)
            new_messages.append(response_message)
            conversation.append(response_message)

            if not (isinstance(response_message, AIMessage) and response_message.tool_calls):
                break

            tool_outputs: list[ToolMessage] = []
            for tool_call in response_message.tool_calls:
                tc_name = tool_call.get("name", "")
                tc_id = tool_call.get("id", "")
                tc_args = tool_call.get("args", {})
                if tc_name not in tools_by_name:
                    tool_outputs.append(
                        ToolMessage(
                            content=f"工具 '{tc_name}' 未找到或暂不可用，请直接作答或调用其他可用工具。",
                            name=tc_name,
                            tool_call_id=tc_id,
                        )
                    )
                    continue
                try:
                    tool_result = await tools_by_name[tc_name].ainvoke(tc_args, config=config)
                    tool_outputs.append(
                        ToolMessage(
                            content=str(tool_result),
                            name=tc_name,
                            tool_call_id=tc_id,
                        )
                    )
                except GraphInterrupt:
                    raise
                except Exception as tool_err:
                    logger.warning(
                        "tutor_tool_invocation_error",
                        session_id=thread_id,
                        node=node,
                        tool=tc_name,
                        error=str(tool_err),
                    )
                    tool_outputs.append(
                        ToolMessage(
                            content=f"工具 '{tc_name}' 执行遇到异常: {str(tool_err)}。请根据当前已有推导直接作答。",
                            name=tc_name,
                            tool_call_id=tc_id,
                        )
                    )
            new_messages.extend(tool_outputs)
            conversation.extend(tool_outputs)

            logger.info(
                "tutor_tool_round_completed",
                session_id=thread_id,
                node=node,
                round=round_idx + 1,
                tool_count=len(tool_outputs),
            )
        else:
            if new_messages and isinstance(new_messages[-1], ToolMessage):
                logger.warning(
                    "tutor_tool_rounds_exhausted",
                    session_id=thread_id,
                    node=node,
                    max_rounds=max_tool_rounds,
                )
                degraded_msg = degrade_tutor_tool_loop(
                    new_messages,
                    RuntimeError("max tool rounds exhausted"),
                )
                return Command(
                    update={
                        "messages": [degraded_msg],
                        "candidate_response": extract_text_content(degraded_msg.content),
                        "intent": state.intent or node,
                    },
                    goto="critic",
                )

        candidate_text = ""
        for msg in reversed(new_messages):
            if isinstance(msg, AIMessage) and msg.content:
                candidate_text = extract_text_content(msg.content)
                break

        for i in range(len(new_messages) - 1, -1, -1):
            if isinstance(new_messages[i], AIMessage) and new_messages[i].content:
                new_messages[i] = AIMessage(
                    content=candidate_text,
                    additional_kwargs=new_messages[i].additional_kwargs,
                    id=new_messages[i].id,
                )
                break

        logger.info(
            "tutor_node_with_tools_completed",
            session_id=thread_id,
            node=node,
            message_count=len(new_messages),
            review_count=state.review_count,
        )
        return Command(
            update={
                "messages": new_messages,
                "candidate_response": candidate_text,
                "intent": state.intent or node,
            },
            goto="critic",
        )
    except GraphInterrupt:
        raise
    except Exception as e:
        logger.warning(
            "tutor_node_with_tools_degraded",
            session_id=thread_id,
            node=node,
            error=str(e),
            partial_messages=len(new_messages),
            rate_limited=is_rate_limit_error(e),
        )
        degraded_msg = degrade_tutor_tool_loop(new_messages, e)
        return Command(
            update={
                "messages": [degraded_msg],
                "candidate_response": extract_text_content(degraded_msg.content),
                "intent": state.intent or node,
            },
            goto="critic",
        )


def make_tutor_node_handlers() -> dict[str, TutorHandler]:
    """Create explain / verify / practice / chat handlers sharing one tool-loop implementation."""

    async def explain(state: GraphState, config: RunnableConfig) -> Command:
        return await run_tutor_with_tools(
            state,
            config,
            node="explain",
            tutor_tools=skill_registry.get_tools_for_node("explain"),
            max_tool_rounds=_DEFAULT_MAX_TOOL_ROUNDS["explain"],
        )

    async def verify(state: GraphState, config: RunnableConfig) -> Command:
        return await run_tutor_with_tools(
            state,
            config,
            node="verify",
            tutor_tools=skill_registry.get_tools_for_node("verify"),
            max_tool_rounds=_DEFAULT_MAX_TOOL_ROUNDS["verify"],
        )

    async def practice(state: GraphState, config: RunnableConfig) -> Command:
        return await run_tutor_with_tools(
            state,
            config,
            node="practice",
            tutor_tools=skill_registry.get_tools_for_node("practice"),
            max_tool_rounds=_DEFAULT_MAX_TOOL_ROUNDS["practice"],
        )

    async def chat(state: GraphState, config: RunnableConfig) -> Command:
        return await run_tutor_with_tools(
            state,
            config,
            node="chat",
            tutor_tools=skill_registry.get_tools_for_node("chat"),
            max_tool_rounds=_DEFAULT_MAX_TOOL_ROUNDS["chat"],
        )

    return {
        "explain": explain,
        "verify": verify,
        "practice": practice,
        "chat": chat,
    }
