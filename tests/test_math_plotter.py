"""Unit tests for math plotter rendering and Chinese character display safety."""

from app.core.langgraph.tools.math_plotter import (
    _format_plot_text,
    _render_function_plot_bytes,
    _sanitize_math_cjk,
)


def test_sanitize_math_cjk():
    """Verify Chinese characters inside math mode ($...$) are properly extracted."""
    # Pure Chinese inside $...$ should become plain text
    assert _sanitize_math_cjk("$二次函数图像$") == "二次函数图像"

    # Colon separated
    assert (
        _sanitize_math_cjk("$二次函数: y = x^2 - 4x + 3$")
        == "二次函数: $y = x^2 - 4x + 3$"
    )

    # Standard LaTeX formula without Chinese remains unchanged
    assert _sanitize_math_cjk("$y = \\sin(x)$") == "$y = \\sin(x)$"


def test_format_plot_text():
    """Verify title and label text formatting with various inputs."""
    # Default fallback
    assert _format_plot_text("", "函数图像: $y = x^2$") == "函数图像: $y = x^2$"

    # Plain Chinese string
    assert _format_plot_text("二次函数图像", "default") == "二次函数图像"

    # Chinese with colon and equation
    assert (
        _format_plot_text("抛物线: y = x**2 - 4*x + 3", "default")
        == "抛物线: $y = x^2 - 4x + 3$"
    )

    # Pure equation without Chinese
    assert (
        _format_plot_text("y = x**2 - 4*x + 3", "default")
        == "$y = x^2 - 4x + 3$"
    )


def test_render_function_plot_bytes():
    """Verify that plotting functions with Chinese title and label generates valid PNG bytes."""
    img_bytes, title = _render_function_plot_bytes(
        expression="x**2 - 4*x + 3",
        x_min=-2.0,
        x_max=6.0,
        title="二次函数图像: y = x^2 - 4x + 3",
        label="抛物线",
    )
    assert len(img_bytes) > 1000
    # PNG signature check
    assert img_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    assert "二次函数图像" in title
