"""LangGraph tools for enhanced language model capabilities.

This package contains custom tools that can be used with LangGraph to extend
the capabilities of language models. Currently includes tools for web search
and other external integrations.
"""

from langchain_core.tools.base import BaseTool

from .ask_human import ask_human
from .math_plotter import plot_math_function
from .python_sandbox import python_sandbox_execute
from .sympy_calculator import sympy_calculate

# Math teacher tools: SymPy calculator, E2B/Python sandbox, Function/Geometry Plotter, and human clarification.
tools: list[BaseTool] = [sympy_calculate, plot_math_function, python_sandbox_execute, ask_human]
