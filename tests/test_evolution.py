"""Unit and integration tests for the agent self-evolution system."""

import pytest
from app.core.prompts import load_node_prompt, load_system_prompt
from app.core.skills import skill_registry
from app.models.evolution import EvolutionPreferencePair
from app.services.database import database_service
from app.services.evolution import DomainReflection, evolution_service


@pytest.fixture
def anyio_backend():
    """Specify asyncio as the default backend for anyio test fixtures."""
    return "asyncio"


def test_domain_reflection_schema():
    """Verify DomainReflection model initialization and defaults."""
    reflection = DomainReflection(
        domain_topic="二次函数顶点与最值",
        pitfall_pattern="忽略 a的正负号导致开口方向判定错误",
        evolved_rule="先判断二次项系数 a的正负，再根据对称轴 x=-b/(2a) 求极值点。",
        recommended_tool_or_heuristic="sympy_calculate / plot_math_function",
    )
    assert reflection.domain_topic == "二次函数顶点与最值"
    assert "忽略 a的正负号" in reflection.pitfall_pattern
    assert "sympy_calculate" in reflection.recommended_tool_or_heuristic


def test_prompt_injection_with_evolved_lessons():
    """Verify that evolved_lessons are seamlessly injected into node and system prompts."""
    lesson = "【避坑原则】：分式方程求解必须在最后一步检验增根（令分母为0的值必须舍去）。"
    system_prompt = load_system_prompt(username="小明", evolved_lessons=lesson)
    assert "历史自进化避坑经验与推导准则" in system_prompt
    assert "分式方程求解必须在最后一步检验增根" in system_prompt

    node_prompt = load_node_prompt("verify", username="小明", evolved_lessons=lesson)
    assert "历史自进化避坑经验与推导准则" in node_prompt
    assert "分式方程求解必须在最后一步检验增根" in node_prompt


def test_dynamic_skill_registration():
    """Verify dynamic skill creation and unregistration."""
    skill_name = "test_geometry_skill"
    skill = skill_registry.register_dynamic_skill(
        name=skill_name,
        display_name="平面几何辅助线推理技能",
        category="geometry",
        description="自动分析角平分线与垂直平分线特征，生成辅助线建议",
        prompt_guidance="- **几何辅助线引导**：遇到角平分线时提示学生构造对称点或垂线段。",
        target_nodes=["explain", "verify"],
    )

    assert skill.name == skill_name
    assert skill_registry.get_skill(skill_name) is not None
    guide = skill_registry.get_prompt_guide_for_node("explain")
    assert "几何辅助线引导" in guide

    # Cleanup
    assert skill_registry.unregister_skill(skill_name) is True
    assert skill_registry.get_skill(skill_name) is None


@pytest.mark.anyio
async def test_evolution_preference_pair_db_and_dpo_export():
    """Verify recording and exporting preference pairs for DPO alignment."""
    pair = EvolutionPreferencePair(
        session_id="test_session_evolution_123",
        user_id="test_user_456",
        intent="verify",
        domain_topic="对数函数定义域",
        prompt="求函数 f(x) = ln(x^2 - 1) 的单调递增区间",
        rejected_response="求导得 f'(x) = 2x/(x^2 - 1)，令 f'(x) > 0 得 x > 0，所以递增区间是 (0, +inf)。",
        chosen_response="首先求定义域：x^2 - 1 > 0 => x > 1 或 x < -1。求导得 f'(x) = 2x/(x^2 - 1)。当 x > 1 时 f'(x) > 0，故单调递增区间为 (1, +inf)。",
        critic_feedback="初次解答遗漏了原对数函数的定义域约束 (x > 1 或 x < -1)，导致区间错误包含 (0, 1]。",
        critic_score=9,
    )

    saved = await database_service.save_evolution_pair(pair)
    assert saved.id is not None

    # Verify query
    pairs = await evolution_service.get_evolution_pairs(limit=10, domain_topic="对数函数定义域")
    assert len(pairs) >= 1
    assert any(p.session_id == "test_session_evolution_123" for p in pairs)

    # Verify DPO export format
    dataset = await evolution_service.export_dpo_dataset(limit=10)
    matching = [d for d in dataset if d["prompt"] == "求函数 f(x) = ln(x^2 - 1) 的单调递增区间"]
    assert len(matching) >= 1
    sample = matching[0]
    assert "chosen" in sample and "rejected" in sample
    assert "首先求定义域" in sample["chosen"]
    assert "x > 0" in sample["rejected"]
