"""Self-Evolution management and DPO preference dataset export endpoints."""

from typing import (
    List,
    Optional,
)

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
)
from pydantic import BaseModel, Field

from app.api.v1.auth import get_current_session
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.core.skills import skill_registry
from app.models.session import Session
from app.services.evolution import evolution_service

router = APIRouter()


class DynamicSkillCreateRequest(BaseModel):
    """Request schema for dynamically registering a new evolved mathematical skill."""

    name: str = Field(description="Unique identifier for skill, e.g. quadratic_optimization")
    display_name: str = Field(description="Display name, e.g. 二次函数最值与极值优化技能")
    category: str = Field(default="algebra", description="Category: algebra, geometry, calculus, statistics")
    description: str = Field(description="Description of mathematical capabilities")
    prompt_guidance: str = Field(description="Instructions to be injected into system prompts")
    target_nodes: Optional[List[str]] = Field(
        default=None,
        description="Target nodes to attach this skill (explain, verify, practice, chat)",
    )


class EvolutionPairResponse(BaseModel):
    """Response schema for an evolution preference pair."""

    id: Optional[int]
    session_id: str
    intent: str
    domain_topic: str
    prompt: str
    rejected_response: str
    chosen_response: str
    critic_feedback: str
    critic_score: int
    created_at: str


class EvolutionStatsResponse(BaseModel):
    """Overview statistics of the self-evolution engine."""

    total_pairs: int
    total_rejected_pairs: int
    registered_skills_count: int


@router.get("/stats", response_model=EvolutionStatsResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["evolution"][0])
async def get_evolution_stats(
    request: Request,
    session: Session = Depends(get_current_session),
):
    """Get statistics on accumulated evolution traces, DPO pairs, and skills."""
    total_count = await evolution_service.count_evolution_pairs()
    all_pairs = await evolution_service.get_evolution_pairs(limit=1000)
    rejected_count = sum(1 for p in all_pairs if p.rejected_response)
    skills = skill_registry.get_all_skills()

    logger.info("evolution_stats_requested", session_id=session.id, total_pairs=total_count)
    return EvolutionStatsResponse(
        total_pairs=total_count,
        total_rejected_pairs=rejected_count,
        registered_skills_count=len(skills),
    )


@router.get("/pairs", response_model=List[EvolutionPairResponse])
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["evolution"][0])
async def list_evolution_pairs(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    topic: Optional[str] = Query(default=None),
    session: Session = Depends(get_current_session),
):
    """Retrieve recorded self-evolution preference pairs."""
    pairs = await evolution_service.get_evolution_pairs(limit=limit, offset=offset, domain_topic=topic)
    return [
        EvolutionPairResponse(
            id=p.id,
            session_id=p.session_id,
            intent=p.intent,
            domain_topic=p.domain_topic,
            prompt=p.prompt,
            rejected_response=p.rejected_response,
            chosen_response=p.chosen_response,
            critic_feedback=p.critic_feedback,
            critic_score=p.critic_score,
            created_at=p.created_at.isoformat(),
        )
        for p in pairs
    ]


@router.get("/dpo-dataset")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["evolution"][0])
async def export_dpo_dataset(
    request: Request,
    limit: int = Query(default=500, ge=1, le=2000),
    session: Session = Depends(get_current_session),
):
    """Export preference dataset formatted for DPO / SFT offline alignment."""
    dataset = await evolution_service.export_dpo_dataset(limit=limit)
    logger.info("dpo_dataset_exported", session_id=session.id, count=len(dataset))
    return {"count": len(dataset), "data": dataset}


@router.get("/reflections")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["evolution"][0])
async def search_reflections(
    request: Request,
    query: str = Query(description="Math question or topic to search reflections for"),
    session: Session = Depends(get_current_session),
):
    """Search global reflexion memory bank for domain lessons and trap avoidance principles."""
    lessons = await evolution_service.search_relevant_reflections(query)
    return {"query": query, "lessons": lessons or "未找到相关历史避坑经验"}


@router.post("/skills/register")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["evolution"][0])
async def register_dynamic_skill(
    request: Request,
    body: DynamicSkillCreateRequest,
    session: Session = Depends(get_current_session),
):
    """Dynamically register a newly discovered mathematical skill into the agent registry."""
    try:
        skill = skill_registry.register_dynamic_skill(
            name=body.name,
            display_name=body.display_name,
            category=body.category,
            description=body.description,
            prompt_guidance=body.prompt_guidance,
            target_nodes=body.target_nodes,
        )
        logger.info("dynamic_skill_registered_via_api", skill_name=body.name, session_id=session.id)
        return {
            "status": "success",
            "message": f"技能 '{skill.display_name}' ({skill.name}) 已成功注册到系统节点。",
            "skill": {
                "name": skill.name,
                "display_name": skill.display_name,
                "category": skill.category,
            },
        }
    except Exception as e:
        logger.exception("dynamic_skill_registration_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
