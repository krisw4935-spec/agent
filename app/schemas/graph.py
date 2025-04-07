"""This file contains the graph schema for the application."""

from typing import Annotated

from langgraph.graph.message import add_messages
from pydantic import (
    BaseModel,
    Field,
)


class GraphState(BaseModel):
    """State definition for the LangGraph Agent/Workflow."""

    messages: Annotated[list, add_messages] = Field(
        default_factory=list, description="The messages in the conversation"
    )
    long_term_memory: str = Field(default="", description="The long term memory of the conversation")
    intent: str = Field(default="", description="Routed tutoring intent for the current turn")
    review_feedback: str = Field(default="", description="Feedback from critic node for rewriting")
    review_count: int = Field(default=0, description="Number of review iterations performed in current turn")
    is_approved: bool = Field(default=True, description="Whether the candidate response passed critic review")
    candidate_response: str = Field(default="", description="The candidate assistant response to be reviewed by critic")
    rejected_first_draft: str = Field(default="", description="First flawed candidate response rejected by Critic, for DPO alignment")
    evolved_lessons: str = Field(default="", description="Domain lessons and trap avoidance rules recalled from global evolution bank")
