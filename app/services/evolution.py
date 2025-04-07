"""Self-Evolution service for continuous reflection, experience accumulation, and DPO data flywheel."""

from typing import (
    List,
    Optional,
)

from langchain_core.messages import HumanMessage
from pydantic import (
    BaseModel,
    Field,
)

from app.core.logging import logger
from app.models.evolution import EvolutionPreferencePair
from app.services.database import database_service
from app.services.llm import llm_service
from app.services.memory import memory_service

GLOBAL_EVOLUTION_USER_ID = "system_global_evolution"


class DomainReflection(BaseModel):
    """Structured mathematical domain reflection extracted from critic evaluations."""

    domain_topic: str = Field(
        default="通用数学",
        description="数学考点或概念分类，如二次函数、导数单调性、分式方程增根、圆锥曲线等",
    )
    pitfall_pattern: str = Field(
        default="",
        description="初次解答容易踩中的逻辑漏洞、定义域遗漏、边界条件忽略或思维盲区",
    )
    evolved_rule: str = Field(
        default="",
        description="提炼出的通用解题避坑准则、严谨推导要求或启发式教学指导规范",
    )
    recommended_tool_or_heuristic: str = Field(
        default="",
        description="推荐调用的自验工具（如 SymPy精确核算、Matplotlib绘图、Python沙箱仿真）或解题策略",
    )


class EvolutionService:
    """Service that manages agent self-evolution, reflexion memory, and DPO preference datasets."""

    async def search_relevant_reflections(self, query: str) -> str:
        """Search the global reflexion bank for domain lessons matching the current query.

        Args:
            query: The student's question text.

        Returns:
            str: Formatted string of accumulated lessons/rules ready for prompt injection.
        """
        if not query or not query.strip():
            return ""

        try:
            memories = await memory_service.search(GLOBAL_EVOLUTION_USER_ID, query)
            if not memories or "No relevant memory found" in memories:
                return ""
            logger.info("global_evolution_reflections_recalled", query_len=len(query))
            return memories
        except Exception as e:
            logger.warning("global_evolution_search_failed", error=str(e))
            return ""

    async def process_turn_evolution(
        self,
        session_id: str,
        prompt: str,
        approved_response: str,
        rejected_response: str = "",
        critic_feedback: str = "",
        critic_score: int = 9,
        intent: str = "solve",
        user_id: Optional[str] = None,
    ) -> None:
        """Asynchronously distill lessons and record DPO preference pair from a completed turn.

        Args:
            session_id: The session thread identifier.
            prompt: The student's question.
            approved_response: The final approved tutor response.
            rejected_response: The initial flawed response rejected by Critic (if any).
            critic_feedback: The critique given by the Critic reviewer.
            critic_score: Quality score given by Critic (1-10).
            intent: Tutoring intent (explain, verify, practice, solve).
            user_id: Optional user identifier.
        """
        if not prompt or not approved_response:
            return

        # Trigger evolution if:
        # 1. Critic rejected an initial candidate and it was subsequently revised (rejected_response exists).
        # 2. Or critic gave a high score (>= 8) providing positive exemplary guidance.
        should_evolve = bool(rejected_response and rejected_response != approved_response) or critic_score >= 8
        if not should_evolve:
            return

        try:
            distillation_prompt = (
                f"你是一个资深数学教育专家与 AI 智能体自进化引擎。\n"
                f"请分析以下解题轨迹中的思考与质检过程，提炼出可沉淀进全局经验库的【考点避坑与推导原则】。\n\n"
                f"【学生题目】：\n{prompt}\n\n"
                + (f"【初次作答不足/被拒初稿】：\n{rejected_response}\n\n" if rejected_response else "")
                + (f"【Critic质检专家意见】：\n{critic_feedback}\n\n" if critic_feedback else "")
                + f"【最终修正/高分正解】：\n{approved_response}\n\n"
                f"请输出结构化的考点、易错陷阱、避坑推导准则及建议调用的核算工具。"
            )

            reflection = await llm_service.call(
                [HumanMessage(content=distillation_prompt)],
                response_format=DomainReflection,
            )

            if not isinstance(reflection, DomainReflection):
                reflection = DomainReflection(
                    domain_topic="初高中数学",
                    pitfall_pattern=critic_feedback or "注意严密推导与边界条件",
                    evolved_rule="先审题并确认定义域/约束条件，再进行代数推演，必要时调用 SymPy/沙箱工具核算。",
                    recommended_tool_or_heuristic="sympy_calculate / python_sandbox_execute",
                )

            # 1. Save to global reflection vector bank for cross-session knowledge transfer
            reflection_content = (
                f"【考点领域】：{reflection.domain_topic}\n"
                f"【思维陷阱/易错点】：{reflection.pitfall_pattern}\n"
                f"【解题与教学准则】：{reflection.evolved_rule}\n"
                f"【推荐验证策略】：{reflection.recommended_tool_or_heuristic}"
            )
            await memory_service.add(
                GLOBAL_EVOLUTION_USER_ID,
                [{"role": "assistant", "content": reflection_content}],
                metadata={
                    "session_id": session_id,
                    "domain_topic": reflection.domain_topic,
                    "critic_score": critic_score,
                },
            )

            # 2. Record preference pair for continuous DPO/SFT alignment
            pair = EvolutionPreferencePair(
                session_id=session_id,
                user_id=user_id,
                intent=intent,
                domain_topic=reflection.domain_topic,
                prompt=prompt,
                rejected_response=rejected_response,
                chosen_response=approved_response,
                critic_feedback=critic_feedback,
                critic_score=critic_score,
            )
            await database_service.save_evolution_pair(pair)

            logger.info(
                "self_evolution_turn_processed",
                session_id=session_id,
                domain_topic=reflection.domain_topic,
                has_rejected_pair=bool(rejected_response),
                critic_score=critic_score,
            )
        except Exception as e:
            logger.exception("self_evolution_processing_failed", session_id=session_id, error=str(e))

    async def get_evolution_pairs(
        self,
        limit: int = 100,
        offset: int = 0,
        domain_topic: Optional[str] = None,
    ) -> List[EvolutionPreferencePair]:
        """Fetch evolution preference pairs from database."""
        return await database_service.get_evolution_pairs(limit=limit, offset=offset, domain_topic=domain_topic)

    async def count_evolution_pairs(self, domain_topic: Optional[str] = None) -> int:
        """Count total evolution preference pairs."""
        return await database_service.count_evolution_pairs(domain_topic=domain_topic)

    async def export_dpo_dataset(self, limit: int = 1000) -> list[dict]:
        """Export preference pairs in standard DPO JSON format for model fine-tuning."""
        pairs = await database_service.get_evolution_pairs(limit=limit)
        dataset: list[dict] = []
        for p in pairs:
            if p.rejected_response:
                dataset.append(
                    {
                        "prompt": p.prompt,
                        "chosen": p.chosen_response,
                        "rejected": p.rejected_response,
                        "feedback": p.critic_feedback,
                        "topic": p.domain_topic,
                        "score": p.critic_score,
                        "created_at": p.created_at.isoformat(),
                    }
                )
        return dataset


evolution_service = EvolutionService()
