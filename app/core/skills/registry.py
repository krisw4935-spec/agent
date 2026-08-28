"""Agent skills registry for domain-specific mathematical tutoring capabilities."""

from typing import Dict, List, Optional

from langchain_core.tools.base import BaseTool

from app.core.langgraph.tools.ask_human import ask_human
from app.core.langgraph.tools.manim_renderer import render_math_animation
from app.core.langgraph.tools.math_plotter import plot_math_function
from app.core.langgraph.tools.python_sandbox import python_sandbox_execute
from app.core.langgraph.tools.sympy_calculator import sympy_calculate
from app.core.logging import logger
from app.core.skills.base import Skill


class SkillRegistry:
    """Registry that manages agent skills, tools, and domain instructions."""

    _QUERY_SKILL_TRIGGERS: Dict[str, tuple[str, ...]] = {
        "algebra_calculus": (
            "计算",
            "求解",
            "解方程",
            "方程",
            "导数",
            "求导",
            "积分",
            "极限",
            "极值",
            "最值",
            "因式分解",
            "零点",
            "顶点",
            "验算",
            "solve",
            "derivative",
            "integral",
        ),
        "math_visualization": (
            "画图",
            "绘图",
            "函数图像",
            "图像",
            "可视化",
            "坐标系",
            "抛物线图",
            "plot",
            "graph",
        ),
        "math_animation": (
            "动画",
            "视频",
            "动态演示",
            "动态展示",
            "manim",
            "animation",
        ),
        "python_sandbox": (
            "python",
            "代码",
            "运行",
            "模拟",
            "仿真",
            "统计",
            "数值",
            "算法",
            "sandbox",
        ),
        "student_clarification": (
            "请选择",
            "选择解法",
            "需要确认",
            "请确认",
        ),
    }

    def __init__(self):
        """Initialize registry and register default skills."""
        self._skills: Dict[str, Skill] = {}
        self._node_skill_mappings: Dict[str, List[str]] = {
            "explain": ["math_visualization", "math_animation", "algebra_calculus", "python_sandbox"],
            "verify": ["algebra_calculus", "math_visualization", "math_animation", "python_sandbox"],
            "practice": ["algebra_calculus", "math_visualization", "math_animation", "python_sandbox"],
            "chat": ["algebra_calculus", "math_visualization", "math_animation", "python_sandbox", "student_clarification"],
        }
        self._register_default_skills()

    def _register_default_skills(self) -> None:
        """Register built-in mathematical skills."""
        # 1. Exact Algebra & Calculus Skill
        self.register(
            Skill(
                name="algebra_calculus",
                display_name="代数与微积分符号核算技能",
                category="symbolic_math",
                description="使用 SymPy 进行精确代数运算、因式分解、方程求解、导数积分与顶点/零点计算。",
                tools=[sympy_calculate],
                prompt_guidance=(
                    "- **代数求解自验**：涉及二次函数零点、极值点、因式分解、方程求解时，调用 `sympy_calculate` 进行精确求解。\n"
                    "  示例：`sympy_calculate(expression='solve(x**2 - 4*x + 3, x)')` 或 `sympy_calculate(expression='vx = -b/(2*a); vy = c - b**2/(4*a); ...')`。"
                ),
            )
        )

        # 2. Math Visualization & Plotting Skill
        self.register(
            Skill(
                name="math_visualization",
                display_name="函数与几何图像可视化技能",
                category="visualization",
                description="自动绘制高质量函数曲线、几何示意图并上传至 MinIO 对象存储生成直链 URL。",
                tools=[plot_math_function],
                prompt_guidance=(
                    "- **数形结合直观呈现**：讲解二次函数、抛物线、三角函数或几何图形时，调用 `plot_math_function` 绘制图像。**重要**：`title` 与 `label` 必须使用标准 LaTeX 公式格式（如 `title='$y = x^2 - 4x + 3$'`, `label='$y = x^2 - 4x + 3$'`），工具返回的 Markdown 图片代码 `![...](url)` 必须原样复制嵌入在你的回答正文中呈现给学生！\n"
                    "  示例：`plot_math_function(expression='x**2 - 4*x + 3', x_min=-1, x_max=5, title='$y = x^2 - 4x + 3$', label='$y = x^2 - 4x + 3$')`。"
                ),
            )
        )

        # 3. Mathematical Animation Skill
        self.register(
            Skill(
                name="math_animation",
                display_name="Manim 数学动画技能",
                category="visualization",
                description="使用 Manim 生成函数、几何、坐标系和推导过程的可播放数学动画。",
                tools=[render_math_animation],
                prompt_guidance=(
                    "- **视频/动画请求是强触发条件**：学生说“生成视频”“视频讲解”“动画演示”“动态展示”或明确提到 Manim 时，"
                    "必须调用 `render_math_animation`，不能只文字回答，也不能用 `plot_math_function` 替代。\n"
                    "  代码必须包含 `from manim import *` 和一个 `Scene` 子类；优先使用 `quality='l'` 预览，复杂动画再使用 `quality='m'`。\n"
                    "  工具会把 MP4 上传到 MinIO；工具返回的 `<video ...>` 播放器和 `[下载数学动画](url)` 链接必须原样复制到最终回答中，"
                    "不要把 Manim Python 代码展示给学生。\n"
                    "  若学生没有要求视频，只有在静态图像不足以说明函数变换、几何构造、证明步骤或动态图形关系时才调用该工具。"
                ),
            )
        )

        # 4. Python Computational Sandbox Skill
        self.register(
            Skill(
                name="python_sandbox",
                display_name="Python 算法与数值仿真沙箱技能",
                category="sandbox",
                description="执行多步骤数值计算、数据统计、迭代算法及自定义几何绘图。",
                tools=[python_sandbox_execute],
                prompt_guidance=(
                    "- **复杂算法与仿真**：当需要复杂数值模拟、统计分析或多步 Python 几何建模时调用 `python_sandbox_execute`。"
                ),
            )
        )

        # 5. Student Intent Clarification & Branch Confirmation Skill
        self.register(
            Skill(
                name="student_clarification",
                display_name="学情诊断与关键决策确认技能",
                category="pedagogy",
                description="在解题中途遇到关键分歧、需要学生确认解题分支或补充关键假设时暂停并等待用户选择确认。",
                tools=[ask_human],
                prompt_guidance=(
                    "- **关键路径确认与中断追问 (ask_human)**：仅在多步解题推导中途遇到多种可选解法路径（例如：选择代数解法还是几何辅助线解法）、或者题目存在重大歧义必须由学生确认分支方可继续时，调用 `ask_human(question='...')` 暂停执行并等待学生选择。\n"
                    "  **注意**：如果是初次问候或普通对话，请直接在正文回复，切勿调用 `ask_human`。"
                ),
            )
        )

    def register(self, skill: Skill) -> None:
        """Register a new domain skill."""
        self._skills[skill.name] = skill
        logger.info("skill_registered", skill_name=skill.name, category=skill.category)

    def register_dynamic_skill(
        self,
        name: str,
        display_name: str,
        category: str,
        description: str,
        prompt_guidance: str,
        tools: Optional[List[BaseTool]] = None,
        target_nodes: Optional[List[str]] = None,
    ) -> Skill:
        """Dynamically create and register a new evolved mathematical skill.

        Args:
            name: Technical identifier for the skill.
            display_name: Human-friendly Chinese name.
            category: Domain classification (e.g. geometry, algebra, statistics).
            description: Summary of skill capability.
            prompt_guidance: Specific prompt instructions for tutor nodes.
            tools: Optional tool instances associated with this skill.
            target_nodes: Optional list of nodes to map this skill to. Defaults to all nodes.

        Returns:
            Skill: The created and registered Skill instance.
        """
        skill = Skill(
            name=name,
            display_name=display_name,
            category=category,
            description=description,
            tools=tools or [],
            prompt_guidance=prompt_guidance,
        )
        self.register(skill)

        nodes = target_nodes or ["explain", "verify", "practice", "chat"]
        for node in nodes:
            if node in self._node_skill_mappings and name not in self._node_skill_mappings[node]:
                self._node_skill_mappings[node].append(name)

        logger.info("dynamic_skill_registered_to_nodes", skill_name=name, nodes=nodes)
        return skill

    def unregister_skill(self, name: str) -> bool:
        """Unregister a skill by name."""
        if name in self._skills:
            del self._skills[name]
            for node_skills in self._node_skill_mappings.values():
                if name in node_skills:
                    node_skills.remove(name)
            logger.info("skill_unregistered", skill_name=name)
            return True
        return False

    def get_skill(self, name: str) -> Optional[Skill]:
        """Retrieve a registered skill by name."""
        return self._skills.get(name)

    def get_all_skills(self) -> List[Skill]:
        """Return all registered skills."""
        return list(self._skills.values())

    def get_tools_for_node(self, node: str) -> List[BaseTool]:
        """Get the combined list of tools for a specific LangGraph tutoring node."""
        skill_names = self._node_skill_mappings.get(
            node,
            ["algebra_calculus", "math_visualization", "math_animation", "python_sandbox"],
        )
        return self.get_tools_for_skills(skill_names)

    def get_tools_for_skills(self, skill_names: List[str]) -> List[BaseTool]:
        """Get the deduplicated tools belonging to the selected skills."""
        tools: List[BaseTool] = []
        for name in skill_names:
            skill = self._skills.get(name)
            if skill:
                for tool in skill.tools:
                    if tool not in tools:
                        tools.append(tool)
        return tools

    def get_skill_names_for_query(self, node: str, query: str) -> List[str]:
        """Select only skills whose capabilities are relevant to the current query."""
        node_skill_names = self._node_skill_mappings.get(
            node,
            ["algebra_calculus", "math_visualization", "math_animation", "python_sandbox"],
        )
        normalized_query = (query or "").casefold()
        return [
            name
            for name in node_skill_names
            if any(trigger.casefold() in normalized_query for trigger in self._QUERY_SKILL_TRIGGERS.get(name, ()))
        ]

    def get_prompt_guide_for_node(self, node: str) -> str:
        """Generate formatted skill guidelines to inject into system prompts."""
        skill_names = self._node_skill_mappings.get(node, [])
        return self.get_prompt_guide_for_skills(skill_names)

    def get_prompt_guide_for_skills(self, skill_names: List[str]) -> str:
        """Generate prompt guidance for only the selected skills."""
        guidance_lines = []
        for name in skill_names:
            skill = self._skills.get(name)
            if skill and skill.prompt_guidance:
                guidance_lines.append(skill.prompt_guidance)
        return "\n".join(guidance_lines)


skill_registry = SkillRegistry()
