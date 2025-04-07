"""Base definitions for agent skills."""

from dataclasses import dataclass, field
from typing import List

from langchain_core.tools.base import BaseTool


@dataclass
class Skill:
    """Represents a domain skill equipped with specialized tools and prompt guidance.

    Attributes:
        name: Unique identifier for the skill.
        display_name: Human-friendly Chinese title for the skill.
        category: High-level category (e.g., 'symbolic_math', 'visualization', 'sandbox').
        description: Brief explanation of what the skill accomplishes.
        tools: Collection of LangChain tools associated with this skill.
        prompt_guidance: Specific instructions given to the agent when utilizing this skill.
    """

    name: str
    display_name: str
    category: str
    description: str
    tools: List[BaseTool] = field(default_factory=list)
    prompt_guidance: str = ""
