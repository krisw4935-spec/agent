"""This file contains the prompts for the agent."""

import os
from datetime import datetime
from typing import Optional

from app.core.config import settings
from app.core.skills import skill_registry

_PROMPTS_DIR = os.path.dirname(__file__)

# Read templates once at module load — no file I/O per request
with open(os.path.join(_PROMPTS_DIR, "system.md"), "r") as _f:
    _SYSTEM_PROMPT_TEMPLATE = _f.read()

with open(os.path.join(_PROMPTS_DIR, "session_title.md"), "r") as _f:
    SESSION_TITLE_PROMPT = _f.read()

with open(os.path.join(_PROMPTS_DIR, "suggested_questions.md"), "r") as _f:
    SUGGESTED_QUESTIONS_PROMPT = _f.read()

_NODE_PROMPT_FILES = {
    "explain": "explain.md",
    "verify": "verify.md",
    "practice": "practice.md",
    "router": "router.md",
    "critic": "critic.md",
}

_NODE_PROMPT_TEMPLATES: dict[str, str] = {}
for _name, _filename in _NODE_PROMPT_FILES.items():
    with open(os.path.join(_PROMPTS_DIR, _filename), "r") as _f:
        _NODE_PROMPT_TEMPLATES[_name] = _f.read()


def _load_template(filename: str) -> str:
    with open(os.path.join(_PROMPTS_DIR, filename), "r", encoding="utf-8") as _f:
        return _f.read()


def _format_user_context(username: Optional[str] = None) -> str:
    return f"# 学生\n你正在辅导 {username}。\n" if username else ""


def load_system_prompt(username: Optional[str] = None, **kwargs) -> str:
    """Load the system prompt from template."""
    template = _load_template("system.md")
    prompt = template.format(
        agent_name=settings.PROJECT_NAME + " 数学老师",
        grade_level=kwargs.get("grade_level", "初高中"),
        current_date_and_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        user_context=_format_user_context(username),
        long_term_memory=kwargs.get("long_term_memory", ""),
    )
    evolved_lessons = kwargs.get("evolved_lessons")
    if evolved_lessons:
        prompt += (
            f"\n\n## 历史自进化避坑经验与推导准则 (Self-Evolved Lessons)\n"
            f"以下是系统在同类数学问题中沉淀的典型避坑法则与严谨性要求，请务必参考遵循：\n{evolved_lessons}\n"
        )
    return prompt


def load_node_prompt(node: str, username: Optional[str] = None, **kwargs) -> str:
    """Load a specialized node prompt (explain, verify, practice, router, critic)."""
    filename = _NODE_PROMPT_FILES.get(node, f"{node}.md")
    template = _load_template(filename)

    if node == "router":
        return template.format(user_message=kwargs.get("user_message", ""))
    if node == "critic":
        return template.format(
            user_context=_format_user_context(username),
            long_term_memory=kwargs.get("long_term_memory", ""),
            candidate_response=kwargs.get("candidate_response", ""),
        )

    base_prompt = template.format(
        agent_name=settings.PROJECT_NAME + " 数学老师",
        grade_level=kwargs.get("grade_level", "初高中"),
        current_date_and_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        user_context=_format_user_context(username),
        long_term_memory=kwargs.get("long_term_memory", ""),
    )

    selected_skill_names = kwargs.get("skill_names")
    skill_guide = (
        skill_registry.get_prompt_guide_for_skills(selected_skill_names)
        if selected_skill_names is not None
        else skill_registry.get_prompt_guide_for_node(node)
    )
    if skill_guide:
        base_prompt += f"\n\n## 推荐调用的专业数学技能 (Registered Skills)\n{skill_guide}\n"

    evolved_lessons = kwargs.get("evolved_lessons")
    if evolved_lessons:
        base_prompt += (
            f"\n\n## 历史自进化避坑经验与推导准则 (Self-Evolved Lessons)\n"
            f"以下是系统在同类数学问题中沉淀的典型避坑法则与严谨性要求，请务必参考遵循：\n{evolved_lessons}\n"
        )

    review_feedback = kwargs.get("review_feedback")
    if review_feedback:
        base_prompt += (
            f"\n\n## 审校专家修改意见 (请务必针对性修正)\n"
            f"上一轮回答未通过质检审校，专家指出的问题如下，请认真修正后重新作答：\n{review_feedback}\n"
        )

    return base_prompt
