"""Evolution data model for storing self-evolution traces and DPO preference pairs."""

from typing import Optional

from sqlmodel import Field

from app.models.base import BaseModel


class EvolutionPreferencePair(BaseModel, table=True):
    """Stores rejected vs chosen candidate responses evaluated by the Critic node.

    Used for:
    1. Continuous DPO / SFT preference alignment data flywheel.
    2. Tracking evolution trajectories across sessions.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True, description="Session/Thread ID where the turn occurred")
    user_id: Optional[str] = Field(default=None, index=True, description="User ID if authenticated")
    intent: str = Field(default="solve", description="Tutoring intent: explain, verify, practice, solve")
    domain_topic: str = Field(default="", description="Mathematical topic or concept category")
    prompt: str = Field(description="Student input question or context")
    rejected_response: str = Field(default="", description="Initial unapproved or lower-quality candidate response")
    chosen_response: str = Field(description="Final approved, pedagogically sound, and mathematically verified response")
    critic_feedback: str = Field(default="", description="Constructive feedback from the Critic reviewer")
    critic_score: int = Field(default=9, description="Quality score from 1 to 10 given by Critic")
