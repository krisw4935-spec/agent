"""Human-in-the-loop confirmation tool for LangGraph.

This module provides a tool that pauses graph execution to ask the user
for confirmation before proceeding with a sensitive action.
"""

from langchain_core.tools import tool
from langgraph.types import interrupt


@tool
def ask_human(question: str) -> str:
    """Pause graph execution and ask the student/user for critical confirmation or branch selection.

    Use this tool ONLY when solving a math problem where there are multiple distinct solution paths
    (e.g., algebraic vs geometric) or key missing parameters that require the user to explicitly choose
    or confirm before continuing the step-by-step derivation.

    Args:
        question: The concise question or choices presented to the user.

    Returns:
        str: The user's response once resumed.
    """
    user_response = interrupt(question)
    return str(user_response)
