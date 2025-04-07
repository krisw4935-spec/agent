"""Routing schema for the math teacher agent."""

from enum import Enum

from pydantic import BaseModel, Field


class MathIntent(str, Enum):
    """High-level tutoring intents routed by the graph."""

    EXPLAIN = "explain"
    VERIFY = "verify"
    PRACTICE = "practice"
    SOLVE = "solve"


class RouterDecision(BaseModel):
    """Structured router output for classifying student messages."""

    intent: MathIntent = Field(description="The tutoring mode that best fits the student message.")
    reasoning: str = Field(description="Brief reason for the chosen intent.")
