"""SymPy calculator tool for exact mathematical and symbolic computation."""

import ast
import re
from typing import Any, cast

from langchain_core.tools import tool
import sympy as sp

from app.core.logging import logger

# Pre-defined common mathematical symbols
_SYMBOLS: dict[str, sp.Symbol] = {
    name: sp.Symbol(name)
    for name in [
        "x", "y", "z", "a", "b", "c", "d", "k", "m", "n", "t", "r",
        "theta", "alpha", "beta", "gamma", "lambda_", "mu", "sigma",
    ]
}

# Rich SymPy namespace with standard math operations
_SYMPY_NS: dict[str, Any] = {
    **_SYMBOLS,
    "sp": sp,
    "sympy": sp,
    "symbols": sp.symbols,
    "Symbol": sp.Symbol,
    "solve": sp.solve,
    "solveset": sp.solveset,
    "roots": sp.roots,
    "diff": sp.diff,
    "integrate": sp.integrate,
    "simplify": sp.simplify,
    "expand": sp.expand,
    "factor": sp.factor,
    "cancel": sp.cancel,
    "together": sp.together,
    "apart": sp.apart,
    "trigsimp": sp.trigsimp,
    "limit": sp.limit,
    "series": sp.series,
    "Eq": sp.Eq,
    "Matrix": sp.Matrix,
    "sqrt": sp.sqrt,
    "cbrt": sp.cbrt,
    "root": sp.root,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "asin": sp.asin,
    "acos": sp.acos,
    "atan": sp.atan,
    "sinh": sp.sinh,
    "cosh": sp.cosh,
    "tanh": sp.tanh,
    "exp": sp.exp,
    "log": sp.log,
    "ln": sp.log,
    "Abs": sp.Abs,
    "abs": sp.Abs,
    "pi": sp.pi,
    "E": sp.E,
    "I": sp.I,
    "oo": sp.oo,
    "zoo": sp.zoo,
    "nan": sp.nan,
    "N": sp.N,
    "evalf": lambda expr, n=6: sp.N(expr, n),
    "latex": sp.latex,
    "Point": sp.Point,
    "Line": sp.Line,
    "Circle": sp.Circle,
    "Triangle": sp.Triangle,
}


def _clean_sympy_code(code: str) -> str:
    """Clean redundant import statements from LLM generated SymPy code."""
    # Replace semicolon separated statements into newlines
    code_with_newlines = re.sub(r";\s*", "\n", code.strip())
    lines = []
    for line in code_with_newlines.splitlines():
        trimmed = line.strip()
        if not trimmed:
            continue
        if re.match(r"^(from\s+sympy(\.\w+)?\s+import|import\s+sympy)", trimmed):
            continue
        lines.append(trimmed)
    return "\n".join(lines).strip()


@tool
def sympy_calculate(expression: str) -> str:
    """Evaluate, simplify, factor, or solve a mathematical expression using SymPy.

    Use for algebra, calculus, equation solving, and exact symbolic manipulation.
    Accepts expressions or multi-step Python SymPy code.
    Common symbols (x, y, z, a, b, c, k, m, n, t) and functions are pre-imported.

    Examples:
        - Solve quadratic equation: "solve(x**2 - 4*x + 3, x)"
        - Factor polynomial: "factor(x**3 - 1)"
        - Derivative: "diff(sin(x)*exp(x), x)"
        - Definite/Indefinite integral: "integrate(x**2, (x, 0, 3))"
        - System of linear equations: "solve([x + y - 5, 2*x - y - 1], [x, y])"
        - Vertex coordinates of parabola: "vx = -b/(2*a); vy = c - b**2/(4*a); (vx.subs({a:1, b:-4}), vy.subs({a:1, b:-4, c:3}))"

    Args:
        expression: Mathematical expression or SymPy computation script.

    Returns:
        Exact computation result as string.
    """
    raw_expr = expression.strip()
    if not raw_expr:
        return "Error: empty expression"

    cleaned_code = _clean_sympy_code(raw_expr)
    if not cleaned_code:
        return "Error: no executable expression found"

    logger.debug("sympy_calculate_executing", raw=raw_expr, cleaned=cleaned_code)

    local_scope = dict(_SYMPY_NS)

    try:
        # 1. Try single expression evaluation first
        parsed_ast = ast.parse(cleaned_code)
        if len(parsed_ast.body) == 1 and isinstance(parsed_ast.body[0], ast.Expr):
            result = eval(cleaned_code, {"__builtins__": {}}, local_scope)
            return str(result)

        # 2. Multi-statement code execution
        # Separate statements and the final expression
        if isinstance(parsed_ast.body[-1], ast.Expr):
            # Execute preceding statements
            module_statements = ast.Module(body=parsed_ast.body[:-1], type_ignores=[])
            compiled_stmts = compile(module_statements, "<sympy_script>", "exec")
            exec(compiled_stmts, {"__builtins__": {}}, local_scope)

            # Evaluate final expression
            expr_ast = ast.Expression(body=parsed_ast.body[-1].value)
            compiled_expr = compile(expr_ast, "<sympy_expr>", "eval")
            result = eval(compiled_expr, {"__builtins__": {}}, local_scope)
            return str(result)
        else:
            # All statements (e.g. assignments), execute all
            compiled_all = compile(parsed_ast, "<sympy_script>", "exec")
            exec(compiled_all, {"__builtins__": {}}, local_scope)
            if "result" in local_scope:
                return str(local_scope["result"])
            # Return last modified variable if any
            custom_vars = {k: v for k, v in local_scope.items() if k not in _SYMPY_NS}
            if custom_vars:
                return ", ".join(f"{k} = {v}" for k, v in custom_vars.items())
            return "Execution completed successfully."

    except Exception as e:
        logger.warning("sympy_calculate_eval_error", raw=raw_expr, error=str(e))
        # 3. Fallback to sp.sympify if possible
        try:
            sym_result = cast(Any, sp.sympify)(raw_expr, locals=_SYMPY_NS)
            return str(sym_result)
        except Exception:
            return f"SymPy computation notice: {e}"
