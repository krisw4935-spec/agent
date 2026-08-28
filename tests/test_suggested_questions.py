"""Unit tests for diverse greeting question generation prompts."""

from app.services.suggested_questions import (
    INSPIRATION_POOL,
    _build_user_prompt,
    _pick_random_inspirations,
)


def test_random_inspirations_are_unique_and_not_grade_partitioned():
    """Ensure each generation can combine unrelated themes without duplicates."""
    inspirations = _pick_random_inspirations()

    assert len(inspirations) == 4
    assert len(set(inspirations)) == 4
    assert len(INSPIRATION_POOL) > 4


def test_generation_prompt_requires_semantic_diversity():
    """Ensure the LLM receives the new non-template generation guidance."""
    inspirations = [
        "校园生活：规划春游路线",
        "运动竞技：比较跑步配速",
        "艺术创作：设计对称图案",
        "数字世界：研究二维码",
    ]
    prompt = _build_user_prompt(inspirations)

    assert all(item in prompt for item in inspirations)
    assert "本轮最重要的目标是发散" in prompt
    assert "不要求固定覆盖小学、初中、高中、综合四种维度" in prompt
    assert "四个问题应尽量在主题场景、数学分支、提问方式和情绪体验上拉开差异" in prompt
