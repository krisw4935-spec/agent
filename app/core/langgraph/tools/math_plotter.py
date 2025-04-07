"""Mathematical plotting and visualization tool for Math Teacher agent."""

import asyncio
import io

from typing import Any, cast

import matplotlib  # type: ignore

matplotlib.use("Agg")  # Non-interactive backend for server environments
import matplotlib.pyplot as plt  # type: ignore
import numpy as np  # type: ignore
from langchain_core.tools import tool
import sympy as sp  # type: ignore

from uuid import uuid4

from app.core.logging import logger
from app.services.storage import storage_service


def _render_function_plot_bytes(
    expression: str,
    x_min: float = -10.0,
    x_max: float = 10.0,
    title: str = "",
    label: str = "",
) -> tuple[bytes, str]:
    """Generate high-quality mathematical function plot and return (image_bytes, plot_title)."""
    x = sp.Symbol("x")
    expr: Any = sp.sympify(expression)
    f_lambdified = sp.lambdify(x, expr, modules=["numpy", "math"])

    # Generate points
    x_vals = np.linspace(x_min, x_max, 400)
    try:
        y_vals = f_lambdified(x_vals)
        if isinstance(y_vals, (int, float)):
            y_vals = np.full_like(x_vals, float(y_vals))
    except Exception:
        # Fallback element-wise evaluation if vectorized fails
        y_list = []
        for xv in x_vals:
            try:
                yv = float(cast(Any, expr.subs(x, xv)).evalf())
                y_list.append(yv)
            except Exception:
                y_list.append(np.nan)
        y_vals = np.array(y_list)

    # Clean extreme values for nice plotting
    y_vals = np.where(np.abs(y_vals) > 1000, np.nan, y_vals)

    # Plot styling
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    plt.rcParams["font.sans-serif"] = [
        "PingFang SC",
        "Heiti SC",
        "Hiragino Sans GB",
        "Microsoft YaHei",
        "SimHei",
        "DejaVu Sans",
        "Arial",
        "sans-serif",
    ]
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=120)

    # Helper for standard LaTeX math formatting in Matplotlib mathtext
    def _to_latex_str(text: str, default_latex: str) -> str:
        if not text:
            return default_latex
        t = text.strip()
        if "$" in t:
            return t
        # Convert plain text exponent and multiplication to LaTeX
        cleaned = t.replace("**", "^").replace("*", "")
        if "=" in cleaned:
            parts = cleaned.split("=", 1)
            return f"${parts[0].strip()} = {parts[1].strip()}$"
        return f"${cleaned}$"

    # Plot curve with standard LaTeX label
    curve_label = _to_latex_str(label, f"$y = {sp.latex(expr)}$")
    ax.plot(x_vals, y_vals, label=curve_label, color="#1f7a5c", linewidth=2.4)

    # Draw standard Cartesian axes
    ax.axhline(0, color="#3a5166", linewidth=1.2, alpha=0.8)
    ax.axvline(0, color="#3a5166", linewidth=1.2, alpha=0.8)

    # Identify and mark roots (zeros) within range
    try:
        roots = sp.solve(expr, x)
        real_roots = []
        for r in roots:
            try:
                rv = float(cast(Any, r).evalf())
                if x_min <= rv <= x_max:
                    real_roots.append(rv)
            except Exception:
                pass

        if real_roots:
            ax.scatter(
                real_roots,
                [0] * len(real_roots),
                color="#c53030",
                s=48,
                zorder=5,
                label=f"零点: {', '.join([f'{r:.2f}' for r in real_roots])}",
            )
    except Exception:
        pass

    # Styling labels and title with LaTeX formula support
    plot_title = _to_latex_str(title, f"函数图像: $y = {sp.latex(expr)}$")
    ax.set_title(plot_title, fontsize=13, pad=12, color="#0b1f33", fontweight="bold")
    ax.set_xlabel("$x$", fontsize=11, color="#3a5166")
    ax.set_ylabel("$y$", fontsize=11, color="#3a5166")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="best", framealpha=0.9)

    plt.tight_layout()

    # Save to memory buffer
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight", dpi=120)
    plt.close(fig)
    buffer.seek(0)
    return buffer.getvalue(), plot_title


@tool
async def plot_math_function(
    expression: str,
    x_min: float = -10.0,
    x_max: float = 10.0,
    title: str = "",
    label: str = "",
) -> str:
    r"""Plot mathematical functions (e.g. parabolas, trigonometric curves, polynomials) and return an embedded visual diagram URL.

    Use this tool whenever explaining function graphs, roots, extrema, symmetry, or geometry to make explanations visual.

    Args:
        expression: Mathematical expression in variable 'x' (e.g., 'x**2 - 4*x + 3', 'sin(x)', '2*x + 1').
        x_min: Minimum x-axis value (default: -10.0).
        x_max: Maximum x-axis value (default: 10.0).
        title: Title of the chart in LaTeX formula format (e.g. '$y = x^2 - 4x + 3$', '$f(x) = \\sin(x)$').
        label: Custom legend label for the curve in LaTeX formula format (e.g. '$y = x^2 - 4x + 3$').

    Returns:
        Markdown embedded image URL string uploaded to MinIO.
    """
    logger.info("math_plotter_called", expression=expression, x_min=x_min, x_max=x_max)
    try:
        img_bytes, plot_title = await asyncio.to_thread(
            _render_function_plot_bytes,
            expression=expression,
            x_min=x_min,
            x_max=x_max,
            title=title,
            label=label,
        )
        filename = f"plot_{uuid4().hex[:10]}.png"
        image_url = await storage_service.upload_image_bytes(img_bytes, filename=filename)
        clean_alt = plot_title.replace("$", "").strip()
        return f"\n\n![{clean_alt}]({image_url})\n\n"
    except Exception as e:
        logger.exception("math_plotter_failed", expression=expression, error=str(e))
        return f"绘图失败: {str(e)}。请检查表达式格式 (如 x**2 - 4*x + 3)。"
