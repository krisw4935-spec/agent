"""Manim mathematical animation renderer tool."""

from __future__ import annotations

import html
from typing import Literal
from uuid import uuid4

import httpx
from langchain_core.tools import tool

from app.core.config import settings
from app.core.logging import logger
from app.services.storage import storage_service

ManimQuality = Literal["l", "m", "h", "p", "k"]
MAX_CODE_LENGTH = 100_000
MAX_TIMEOUT_SECONDS = 900


def _get_render_error(response: httpx.Response) -> str:
    """Extract a useful error message from the rendering service response."""
    try:
        payload = response.json()
        if isinstance(payload, dict) and payload.get("detail"):
            return str(payload["detail"])
    except (ValueError, TypeError):
        pass
    return response.text.strip() or f"HTTP {response.status_code}"


def _video_markdown(video_url: str) -> str:
    """Build the player markup returned to the tutor for final-answer embedding."""
    safe_url = html.escape(video_url, quote=True)
    return (
        "\n\n### 数学动画\n\n"
        f'<video controls preload="metadata" src="{safe_url}" '
        f'title="数学动画">您的浏览器不支持视频播放，请<a href="{safe_url}">下载视频</a>。</video>\n\n'
        f"[下载数学动画]({video_url})\n\n"
    )


@tool
async def render_math_animation(
    code: str,
    scene_name: str = "",
    quality: ManimQuality = "l",
    timeout: int | None = None,
) -> str:
    """Render a mathematical animation from Manim Python code and return a playable video.

    Use this tool for dynamic visual explanations such as function transformations,
    geometric constructions, proof animations, coordinate systems, and step-by-step
    mathematical derivations. The code must define at least one ``Scene`` subclass.

    Args:
        code: Complete Manim Python source code containing a Scene subclass.
        scene_name: Optional Scene class name. The renderer auto-selects the first Scene when omitted.
        quality: Manim quality: l (preview), m, h, p, or k (4K).
        timeout: Optional render timeout in seconds, from 1 to 900.

    Returns:
        HTML video markup and a Markdown download link for the generated MP4.
    """
    if not settings.MANIM_ENABLED:
        return "数学动画服务当前未启用，请使用文字和静态图像完成讲解。"

    if not code.strip():
        return "数学动画生成失败：Manim 代码不能为空。"
    if len(code) > MAX_CODE_LENGTH:
        return f"数学动画生成失败：代码长度不能超过 {MAX_CODE_LENGTH} 个字符。"
    if scene_name and not scene_name.isidentifier():
        return "数学动画生成失败：scene_name 必须是合法的 Python 类名。"

    render_timeout = timeout if timeout is not None else settings.MANIM_RENDER_TIMEOUT
    if render_timeout < 1 or render_timeout > MAX_TIMEOUT_SECONDS:
        return f"数学动画生成失败：timeout 必须在 1 到 {MAX_TIMEOUT_SECONDS} 秒之间。"

    payload = {
        "code": code,
        "scene_name": scene_name or None,
        "quality": quality,
        "timeout": render_timeout,
    }
    logger.info(
        "math_animation_render_started",
        code_length=len(code),
        scene_name=scene_name or "auto",
        quality=quality,
        timeout=render_timeout,
    )

    try:
        request_timeout = httpx.Timeout(render_timeout + 15.0, connect=5.0)
        async with httpx.AsyncClient(timeout=request_timeout) as client:
            response = await client.post(settings.MANIM_RENDER_URL, json=payload)

        if response.status_code != 200:
            error = _get_render_error(response)
            logger.warning("math_animation_render_failed", status_code=response.status_code, error=error)
            return f"数学动画生成失败：{error}"

        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type != "video/mp4" or not response.content:
            logger.warning(
                "math_animation_invalid_response",
                content_type=content_type,
                response_size=len(response.content),
            )
            return "数学动画生成失败：渲染服务没有返回有效的 MP4 视频。"

        filename = f"animation_{uuid4().hex[:12]}.mp4"
        video_url = await storage_service.upload_bytes(
            data=response.content,
            filename=filename,
            content_type="video/mp4",
        )
        logger.info(
            "math_animation_render_completed",
            filename=filename,
            size_bytes=len(response.content),
            video_url=video_url,
        )
        return _video_markdown(video_url)
    except httpx.TimeoutException:
        logger.warning("math_animation_render_timeout", timeout=render_timeout)
        return f"数学动画生成超时：超过 {render_timeout} 秒，请降低 quality 或缩短动画。"
    except httpx.HTTPError as exc:
        logger.warning("math_animation_service_unreachable", error=str(exc))
        return "数学动画服务暂时不可用，请确认 Manim 服务已启动。"
    except Exception as exc:
        logger.exception("math_animation_tool_failed", error=str(exc))
        return f"数学动画生成失败：{exc}"
