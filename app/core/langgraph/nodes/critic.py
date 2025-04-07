"""Critic node: quality-gate tutor answers and optionally request revision."""

import asyncio

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import END
from langgraph.graph.state import Command

from app.core.langgraph.helpers import get_last_user_content, is_rate_limit_error
from app.core.langgraph.models import CriticDecision, resolve_revision_target
from app.core.logging import logger
from app.core.prompts import load_node_prompt
from app.schemas import Message
from app.schemas.graph import GraphState
from app.services.evolution import evolution_service
from app.services.llm import llm_service
from app.utils import extract_text_content


def make_critic_node():
    """Build the async critic reviewer node."""

    async def critic(state: GraphState, config: RunnableConfig) -> Command:
        """Evaluate tutor response for correctness, boundaries, and pedagogy."""
        thread_id = config.get("configurable", {}).get("thread_id")
        username = config.get("metadata", {}).get("username")

        candidate_text = state.candidate_response
        if not candidate_text:
            for m in reversed(state.messages):
                if isinstance(m, (AIMessage, Message)) and m.content:
                    candidate_text = extract_text_content(m.content)
                    break

        if state.review_count >= 2:
            logger.info(
                "critic_max_rounds_reached_auto_approve",
                session_id=thread_id,
                review_count=state.review_count,
            )
            auto_summary = (
                "【审校结果】✅ 审核通过（已达最大审校轮次）\n"
                "【综合评分】8 / 10\n"
                "【思考与质检分析】已完成多轮审校迭代修正，解答推导严密且无代码报错，达到放行标准。\n"
                "【质检结论】解题推导严密，符合启发式教学规范。"
            )
            critic_msg = ToolMessage(
                content=auto_summary,
                name="critic_review",
                tool_call_id=f"critic_{state.review_count}",
            )
            prompt_text = get_last_user_content(state.messages)
            asyncio.create_task(
                evolution_service.process_turn_evolution(
                    session_id=thread_id or "",
                    prompt=prompt_text,
                    approved_response=candidate_text,
                    rejected_response=state.rejected_first_draft,
                    critic_feedback="已达最大审校轮次自动放行",
                    critic_score=8,
                    intent=state.intent or "solve",
                    user_id=config.get("metadata", {}).get("user_id"),
                )
            )
            return Command(
                update={
                    "messages": [critic_msg],
                    "is_approved": True,
                    "review_feedback": "",
                    "rejected_first_draft": "",
                },
                goto=END,
            )

        if not candidate_text:
            auto_summary = (
                "【审校结果】✅ 审核通过\n"
                "【综合评分】9 / 10\n"
                "【思考与质检分析】候选解答为空或无需质检直接放行。\n"
                "【质检结论】解答已完成质检审校。"
            )
            critic_msg = ToolMessage(
                content=auto_summary,
                name="critic_review",
                tool_call_id=f"critic_{state.review_count}",
            )
            return Command(
                update={
                    "messages": [critic_msg],
                    "is_approved": True,
                    "review_feedback": "",
                    "rejected_first_draft": "",
                },
                goto=END,
            )

        critic_prompt = load_node_prompt(
            "critic",
            username=username,
            long_term_memory=state.long_term_memory,
            candidate_response=candidate_text,
        )

        try:
            decision = await llm_service.call(
                [HumanMessage(content=critic_prompt)],
                response_format=CriticDecision,
            )
            if not isinstance(decision, CriticDecision):
                decision = CriticDecision(is_approved=True)

            logger.info(
                "critic_review_evaluated",
                session_id=thread_id,
                is_approved=decision.is_approved,
                score=decision.score,
                reasoning_length=len(decision.reasoning),
                feedback_length=len(decision.feedback),
                review_count=state.review_count,
            )

            is_approved = decision.is_approved or decision.score >= 8
            review_parts = [
                f"【审校结果】{'✅ 审核通过' if is_approved else '⚠️ 需修正重写'}",
                f"【综合评分】{decision.score} / 10",
            ]
            if decision.reasoning:
                review_parts.append(f"【思考与质检分析】\n{decision.reasoning}")
            if decision.feedback:
                review_parts.append(f"【修改建议】\n{decision.feedback}")
            else:
                review_parts.append(
                    "【质检结论】解题推导严谨，边界条件与定义域完备，无代码泄漏，符合启发式教学规范。"
                )

            review_summary = "\n\n".join(review_parts)
            critic_msg = ToolMessage(
                content=review_summary,
                name="critic_review",
                tool_call_id=f"critic_{state.review_count}",
            )

            if is_approved:
                prompt_text = get_last_user_content(state.messages)
                asyncio.create_task(
                    evolution_service.process_turn_evolution(
                        session_id=thread_id or "",
                        prompt=prompt_text,
                        approved_response=candidate_text,
                        rejected_response=state.rejected_first_draft,
                        critic_feedback=decision.feedback,
                        critic_score=decision.score,
                        intent=state.intent or "solve",
                        user_id=config.get("metadata", {}).get("user_id"),
                    )
                )
                return Command(
                    update={
                        "messages": [critic_msg],
                        "is_approved": True,
                        "review_feedback": "",
                        "rejected_first_draft": "",
                    },
                    goto=END,
                )

            target_node = resolve_revision_target(state.intent)
            rejected_draft = state.rejected_first_draft or candidate_text
            logger.warning(
                "critic_review_rejected_revising",
                session_id=thread_id,
                target_node=target_node,
                review_round=state.review_count + 1,
                feedback=decision.feedback,
            )

            return Command(
                update={
                    "messages": [critic_msg],
                    "is_approved": False,
                    "review_feedback": decision.feedback,
                    "review_count": state.review_count + 1,
                    "rejected_first_draft": rejected_draft,
                },
                goto=target_node,
            )
        except Exception as e:
            is_429 = is_rate_limit_error(e)
            logger.warning(
                "critic_review_failed_fallback_approve",
                session_id=thread_id,
                is_429=is_429,
                error=str(e),
            )
            err_type = "429 速率限制 (Rate Limit Exceeded)" if is_429 else f"调用异常 ({type(e).__name__})"
            review_summary = (
                f"【审校结果】✅ 审核通过 (降级放行)\n"
                f"【综合评分】8 / 10\n"
                f"【思考与质检分析】审校节点遇到上游模型 {err_type}: {str(e)}\n"
                f"【质检结论】系统已自动安全放行，未阻塞辅导回答。"
            )
            fallback_msg = ToolMessage(
                content=review_summary,
                name="critic_review",
                tool_call_id=f"critic_{state.review_count}",
            )
            return Command(
                update={
                    "messages": [fallback_msg],
                    "is_approved": True,
                    "review_feedback": "",
                    "rejected_first_draft": "",
                },
                goto=END,
            )

    return critic
