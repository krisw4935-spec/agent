"""Python sandbox execution tool using E2B Code Interpreter with local fallback."""

import asyncio
import base64
import io
import math
import statistics
import sys
import traceback
from typing import Any
from uuid import uuid4

from e2b_code_interpreter import AsyncSandbox
from langchain_core.tools import tool

from app.core.config import settings
from app.core.langgraph.tools.math_plotter import CHINESE_FONT_FAMILY
from app.core.logging import logger
from app.services.storage import storage_service

E2B_PREAMBLE: str = """
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = [
        "PingFang SC", "Hiragino Sans GB", "Heiti SC", "STHeiti",
        "Microsoft YaHei", "SimHei", "WenQuanYi Micro Hei", "WenQuanYi Zen Hei",
        "Noto Sans CJK SC", "Source Han Sans CN", "Arial Unicode MS", "DejaVu Sans", "sans-serif"
    ]
    plt.rcParams["axes.unicode_minus"] = False
except Exception:
    pass
"""


def _execute_code_local(code: str) -> str:
    """Execute Python code in local safe namespace as a fallback."""
    # Ensure matplotlib Chinese fonts are preconfigured if matplotlib is available
    try:
        import matplotlib  # type: ignore

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore

        plt.rcParams["font.sans-serif"] = CHINESE_FONT_FAMILY
        plt.rcParams["axes.unicode_minus"] = False
    except Exception:
        pass
    safe_globals: dict[str, Any] = {
        "__builtins__": {
            "abs": abs,
            "all": all,
            "any": any,
            "bin": bin,
            "bool": bool,
            "dict": dict,
            "divmod": divmod,
            "enumerate": enumerate,
            "filter": filter,
            "float": float,
            "format": format,
            "frozenset": frozenset,
            "hex": hex,
            "int": int,
            "isinstance": isinstance,
            "issubclass": issubclass,
            "iter": iter,
            "len": len,
            "list": list,
            "map": map,
            "max": max,
            "min": min,
            "next": next,
            "oct": oct,
            "pow": pow,
            "print": print,
            "range": range,
            "repr": repr,
            "reversed": reversed,
            "round": round,
            "set": set,
            "slice": slice,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "type": type,
            "zip": zip,
            "__import__": __import__,
        },
        "math": math,
        "statistics": statistics,
    }

    try:
        import sympy  # type: ignore

        safe_globals["sympy"] = sympy
        safe_globals["sp"] = sympy
    except ImportError:
        pass

    try:
        import numpy as np  # type: ignore

        safe_globals["numpy"] = np
        safe_globals["np"] = np
    except ImportError:
        pass

    try:
        import scipy  # type: ignore

        safe_globals["scipy"] = scipy
    except ImportError:
        pass

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    old_stdout = sys.stdout
    old_stderr = sys.stderr

    local_namespace: dict[str, Any] = {}

    try:
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture
        exec(code, safe_globals, local_namespace)
        output = stdout_capture.getvalue()
        errors = stderr_capture.getvalue()

        result_parts = []
        if output:
            result_parts.append(f"STDOUT:\n{output.strip()}")
        if errors:
            result_parts.append(f"STDERR:\n{errors.strip()}")
        if "result" in local_namespace:
            result_parts.append(f"RESULT: {local_namespace['result']}")

        # Capture any plotted matplotlib figures and upload to MinIO
        try:
            if "matplotlib.pyplot" in sys.modules:
                import matplotlib.pyplot as plt  # type: ignore

                if plt.get_fignums():
                    fig = plt.gcf()
                    img_buf = io.BytesIO()
                    fig.savefig(img_buf, format="png", bbox_inches="tight", dpi=120)
                    plt.close("all")
                    img_bytes = img_buf.getvalue()
                    filename = f"geom_{uuid4().hex[:10]}.png"
                    img_url = storage_service.upload_image_bytes_sync(img_bytes, filename=filename)
                    result_parts.append(f"\n\n![示意图]({img_url})\n\n")
        except Exception as plot_err:
            logger.debug("matplotlib_figure_capture_skipped", error=str(plot_err))

        if not result_parts:
            return "Code executed successfully with no output. (Tip: Use print() or set a `result` variable to see output)"

        return "\n\n".join(result_parts)
    except Exception as e:
        error_type = type(e).__name__
        tb_lines = traceback.format_exc().splitlines()
        short_tb = "\n".join(tb_lines[-3:]) if len(tb_lines) >= 3 else str(e)
        return f"EXECUTION_ERROR [{error_type}]: {str(e)}\nTraceback:\n{short_tb}\n(Tip: Check your syntax and variable definitions to self-debug.)"
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


async def _execute_in_e2b(code: str) -> str:
    """Execute code in an isolated E2B Code Interpreter sandbox."""
    api_key = settings.E2B_API_KEY
    if not api_key:
        raise ValueError("e2b_api_key_not_configured")

    sandbox = await AsyncSandbox.create(api_key=api_key)
    try:
        # Prepend font/matplotlib initialization if code utilizes matplotlib
        exec_code = f"{E2B_PREAMBLE}\n{code}" if "plt" in code or "matplotlib" in code else code
        execution = await sandbox.run_code(exec_code)
        result_parts: list[str] = []

        if execution.logs and execution.logs.stdout:
            stdout_text = "".join(execution.logs.stdout).strip()
            if stdout_text:
                result_parts.append(f"STDOUT:\n{stdout_text}")

        if execution.logs and execution.logs.stderr:
            stderr_text = "".join(execution.logs.stderr).strip()
            if stderr_text:
                result_parts.append(f"STDERR:\n{stderr_text}")

        if execution.text:
            result_parts.append(f"RESULT:\n{execution.text.strip()}")

        # Capture any matplotlib figures rendered in E2B sandbox
        if execution.results:
            for res in execution.results:
                png_raw = getattr(res, "png", None)
                if png_raw:
                    try:
                        img_bytes = base64.b64decode(png_raw) if isinstance(png_raw, str) else png_raw
                        filename = f"e2b_geom_{uuid4().hex[:10]}.png"
                        img_url = await storage_service.upload_image_bytes(img_bytes, filename=filename)
                        result_parts.append(f"\n\n![示意图]({img_url})\n\n")
                    except Exception as img_err:
                        logger.warning("e2b_image_upload_failed", error=str(img_err))

        if execution.error:
            err_name = execution.error.name or "RuntimeError"
            err_val = execution.error.value or ""
            err_tb = execution.error.traceback or ""
            result_parts.append(
                f"EXECUTION_ERROR [{err_name}]: {err_val}\nTraceback:\n{err_tb}\n(Tip: Self-debug by fixing syntax or logic errors indicated in the traceback.)"
            )

        if not result_parts:
            return "Code executed successfully in E2B sandbox with no output. (Tip: Use print() to inspect results)"

        return "\n\n".join(result_parts)
    finally:
        try:
            await sandbox.kill()
        except Exception as e:
            logger.warning("failed_to_kill_e2b_sandbox", error=str(e))


@tool
async def python_sandbox_execute(code: str) -> str:
    """Execute Python code in an isolated cloud sandbox (E2B Code Interpreter) to verify calculations, solve equations, and test proofs.

    Available libraries: math, sympy, numpy, scipy, statistics, matplotlib, etc.
    Usage tips:
      - Use `print(...)` to display intermediate or final results.
      - Useful for solving algebraic equations, calculating derivatives/integrals, simulating geometric configurations,
        and validating student answers with exact computation.

    Args:
        code: Python source code string to execute.

    Returns:
        Standard output, returned values, or execution error traceback for self-debugging.
    """
    logger.info("sandbox_code_execution_started", code_length=len(code))

    # 1. Try E2B Sandbox first if API key is provided
    if settings.E2B_API_KEY:
        try:
            result = await _execute_in_e2b(code)
            logger.info("sandbox_code_execution_completed_e2b", output_length=len(result))
            return result
        except Exception as e:
            logger.warning(
                "e2b_execution_failed_falling_back_to_local",
                error=str(e),
                code_length=len(code),
            )

    # 2. Fallback to local controlled sandbox
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_execute_code_local, code),
            timeout=5.0,
        )
        logger.info("sandbox_code_execution_completed_local", output_length=len(result))
        return result
    except asyncio.TimeoutError:
        logger.warning("sandbox_code_execution_timeout", code_length=len(code))
        return "EXECUTION_ERROR: Execution timed out after 5.0 seconds. Avoid infinite loops or excessively large computations."
    except Exception as e:
        logger.exception("sandbox_code_execution_failed", error=str(e))
        return f"EXECUTION_ERROR: {str(e)}"
