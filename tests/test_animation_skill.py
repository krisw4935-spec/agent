"""Tests for explicit mathematical animation requests."""

from langchain_core.messages import AIMessage

from app.core.langgraph.helpers import is_animation_request
from app.core.langgraph.helpers import extract_manim_code
from app.core.langgraph.nodes.tutors import _build_tutor_prompt
from app.schemas import Message
from app.schemas.graph import GraphState


def test_is_animation_request_detects_video_intent() -> None:
    """Explicit video language should activate the animation skill."""
    assert is_animation_request("请生成一个视频讲解同底等高的三角形")
    assert is_animation_request("用 Manim 动态演示圆的切线")


def test_is_animation_request_respects_negation() -> None:
    """A request that rejects animation should not activate the skill."""
    assert not is_animation_request("不要视频，只需要文字讲解")
    assert not is_animation_request("不需要动画")


def test_animation_prompt_requires_render_tool() -> None:
    """Animation requests should add mandatory render-and-return instructions."""
    state = GraphState(messages=[Message(role="user", content="生成一个生动的视频讲解三角形面积")])

    prompt = _build_tutor_prompt("explain", state, username=None)

    assert "视频动画任务（高优先级，必须执行）" in prompt
    assert "`render_math_animation`" in prompt
    assert "MinIO 下载链接" in prompt


def test_extract_manim_code_recovers_reasoning_code_block() -> None:
    """A complete code block in reasoning should be usable as a render fallback."""
    message = AIMessage(
        content="",
        additional_kwargs={
            "reasoning_content": (
                "我来生成动画：\n"
                "```python\n"
                "from manim import *\n"
                "class Demo(Scene):\n"
                "    def construct(self):\n"
                "        self.play(Create(Circle()))\n"
                "```\n"
            )
        },
    )

    assert extract_manim_code(message).startswith("from manim import *")
