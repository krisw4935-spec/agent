"""High-performance Hierarchical Hybrid Router for classifying student tutoring intents.

Multi-tier routing pipeline:
1. Level 1: Explicit Prefixes & Heuristic Rules (~0ms)
2. Level 2: Local Semantic Similarity Scorer (~1ms)
3. Level 3: Safe Fallback to SOLVE mode (~0ms)
"""

import math
import re
from typing import NamedTuple

from app.core.logging import logger
from app.schemas.routing import MathIntent, RouterDecision


class SemanticAnchor(NamedTuple):
    """Anchor utterance representation for semantic matching."""

    intent: MathIntent
    text: str
    char_ngrams: set[str]


def _build_char_ngrams(text: str, n: int = 2) -> set[str]:
    """Generate character n-grams for robust substring/semantic overlap matching."""
    cleaned = re.sub(r"\s+", "", text.lower())
    if len(cleaned) < n:
        return {cleaned} if cleaned else set()
    return {cleaned[i : i + n] for i in range(len(cleaned) - n + 1)}


def _cosine_similarity(ngrams_a: set[str], ngrams_b: set[str]) -> float:
    """Compute cosine similarity between two n-gram sets."""
    if not ngrams_a or not ngrams_b:
        return 0.0
    intersection_size = len(ngrams_a & ngrams_b)
    if intersection_size == 0:
        return 0.0
    return intersection_size / math.sqrt(len(ngrams_a) * len(ngrams_b))


class RouterService:
    """Service to classify incoming mathematical tutor queries quickly and deterministically."""

    # Explicit prefix mappings (e.g. from UI tags or user commands)
    PREFIX_MAP: dict[str, MathIntent] = {
        "[explain]": MathIntent.EXPLAIN,
        "[verify]": MathIntent.VERIFY,
        "[practice]": MathIntent.PRACTICE,
        "[solve]": MathIntent.SOLVE,
        "【讲解】": MathIntent.EXPLAIN,
        "【概念讲解】": MathIntent.EXPLAIN,
        "【批改】": MathIntent.VERIFY,
        "【解题批改】": MathIntent.VERIFY,
        "【练习】": MathIntent.PRACTICE,
        "【出题】": MathIntent.PRACTICE,
        "【靶向练习】": MathIntent.PRACTICE,
        "【解题】": MathIntent.SOLVE,
        "【综合解题】": MathIntent.SOLVE,
        "/explain": MathIntent.EXPLAIN,
        "/verify": MathIntent.VERIFY,
        "/practice": MathIntent.PRACTICE,
        "/solve": MathIntent.SOLVE,
    }

    # Keyword rules for Level 1 fast path
    VERIFY_KEYWORDS: tuple[str, ...] = (
        "我的解答",
        "我的解法",
        "我的步骤",
        "帮我批改",
        "批改一下",
        "检查我的",
        "对不对",
        "有没有错",
        "算错了吗",
        "做得对吗",
        "帮我看看第",
        "verify",
        "check my",
    )

    PRACTICE_KEYWORDS: tuple[str, ...] = (
        "出题",
        "出几道",
        "来一道",
        "再来一题",
        "出类似题",
        "设计练习",
        "练习题",
        "做点题",
        "做测试",
        "测验",
        "靶向练习",
        "考考我",
        "practice",
        "quiz",
    )

    EXPLAIN_KEYWORDS: tuple[str, ...] = (
        "什么是",
        "为什么",
        "讲解",
        "解释一下",
        "几何意义",
        "物理意义",
        "是什么意思",
        "怎么理解",
        "如何理解",
        "定理含义",
        "公式推导",
        "直观理解",
        "explain",
    )

    SOLVE_KEYWORDS: tuple[str, ...] = (
        "解方程",
        "求解",
        "计算",
        "证明",
        "求导",
        "求极限",
        "求极值",
        "求最值",
        "积分",
        "求:",
        "求：",
        "已知",
        "设函数",
        "若",
        "solve",
        "∫",
        "\\int",
        "\\lim",
        "\\frac",
    )

    # Level 2 Semantic anchors for intent classification
    RAW_ANCHORS: list[tuple[MathIntent, str]] = [
        # EXPLAIN
        (MathIntent.EXPLAIN, "什么是泰勒展开公式及其几何含义"),
        (MathIntent.EXPLAIN, "请帮我讲解一下二阶导数的直观概念"),
        (MathIntent.EXPLAIN, "为什么两点之间线段最短如何证明"),
        (MathIntent.EXPLAIN, "柯西施瓦茨不等式的本质是什么"),
        (MathIntent.EXPLAIN, "如何直观理解复数和欧拉公式"),
        (MathIntent.EXPLAIN, "请详细解释极限的保号性"),
        # VERIFY
        (MathIntent.VERIFY, "这是我算的导数过程，麻烦老师帮我检查对不对"),
        (MathIntent.VERIFY, "我解出的答案是x=5，请帮我批改一下步骤"),
        (MathIntent.VERIFY, "请看一下我的证明步骤有没有逻辑漏洞"),
        (MathIntent.VERIFY, "这是我的作业解答，请老师指出错误"),
        (MathIntent.VERIFY, "我用换元法做出来了，帮我验算一下结果"),
        # PRACTICE
        (MathIntent.PRACTICE, "我想巩固一下三角恒等变换，请给我出3道练习题"),
        (MathIntent.PRACTICE, "出一道高中导数压轴题考考我"),
        (MathIntent.PRACTICE, "针对二次函数的知识点，再生成一道练习题"),
        (MathIntent.PRACTICE, "请出一份包含5道定积分计算的选择题测验"),
        (MathIntent.PRACTICE, "再来一道类似的解析几何大题"),
        # SOLVE
        (MathIntent.SOLVE, "已知函数f(x)=x^3-3x+1，求单调递增区间和极值"),
        (MathIntent.SOLVE, "计算定积分从0到1对x*exp(x)的积分"),
        (MathIntent.SOLVE, "解方程组2x+y=5且x-3y=2"),
        (MathIntent.SOLVE, "求椭圆x^2/16+y^2/9=1的离心率和焦点坐标"),
        (MathIntent.SOLVE, "证明数列在n趋于无穷大时的收敛性"),
    ]

    def __init__(self, similarity_threshold: float = 0.35) -> None:
        """Initialize the router service and precompute semantic anchors."""
        self.similarity_threshold = similarity_threshold
        self._anchors: list[SemanticAnchor] = [
            SemanticAnchor(intent=intent, text=text, char_ngrams=_build_char_ngrams(text))
            for intent, text in self.RAW_ANCHORS
        ]

    def route(self, user_message: str) -> RouterDecision:
        """Classify user message using Hierarchical Hybrid routing.

        Returns:
            RouterDecision: Tuple with selected MathIntent and reasoning string.
        """
        raw_text = (user_message or "").strip()
        if not raw_text:
            return RouterDecision(
                intent=MathIntent.SOLVE,
                reasoning="学生输入为空，默认进入综合求解与答疑模式 (solve)。",
            )

        lower_text = raw_text.lower()

        # --- Level 1.1: Explicit Prefix Matching ---
        for prefix, intent in self.PREFIX_MAP.items():
            if lower_text.startswith(prefix.lower()):
                intent_label = intent.value
                logger.info("router_explicit_prefix_matched", prefix=prefix, intent=intent_label)
                return RouterDecision(
                    intent=intent,
                    reasoning=f"命中显式意图指令 '{prefix}'，直接规划为【{intent_label}】模式。",
                )

        # --- Level 1.2: Heuristic Feature Rules ---
        if any(h in lower_text for h in self.VERIFY_KEYWORDS):
            logger.info("router_heuristic_matched", rule="verify", intent="verify")
            return RouterDecision(
                intent=MathIntent.VERIFY,
                reasoning="检测到学生提交解法或请求检查批改的特征词，规划为【解题批改 (verify)】模式。",
            )

        if any(h in lower_text for h in self.PRACTICE_KEYWORDS):
            logger.info("router_heuristic_matched", rule="practice", intent="practice")
            return RouterDecision(
                intent=MathIntent.PRACTICE,
                reasoning="检测到出题/做题/练习请求的特征词，规划为【靶向练习 (practice)】模式。",
            )

        # Explain check: Ensure it's not a solve statement like "解释一下这道题的求解过程: 解方程..."
        if any(h in lower_text for h in self.EXPLAIN_KEYWORDS) and "解方程" not in lower_text:
            logger.info("router_heuristic_matched", rule="explain", intent="explain")
            return RouterDecision(
                intent=MathIntent.EXPLAIN,
                reasoning="检测到概念探究、定理含义或原理询问特征，规划为【概念精讲 (explain)】模式。",
            )

        if any(h in lower_text for h in self.SOLVE_KEYWORDS):
            logger.info("router_heuristic_matched", rule="solve", intent="solve")
            return RouterDecision(
                intent=MathIntent.SOLVE,
                reasoning="检测到具体的数学题目、算式或求解要求，规划为【综合求解 (solve)】模式。",
            )

        # --- Level 2: Semantic Similarity via Anchor Overlap ---
        query_ngrams = _build_char_ngrams(raw_text)
        best_intent: MathIntent | None = None
        best_score = 0.0
        best_anchor_text = ""

        for anchor in self._anchors:
            score = _cosine_similarity(query_ngrams, anchor.char_ngrams)
            if score > best_score:
                best_score = score
                best_intent = anchor.intent
                best_anchor_text = anchor.text

        if best_intent is not None and best_score >= self.similarity_threshold:
            logger.info(
                "router_semantic_anchor_matched",
                intent=best_intent.value,
                score=round(best_score, 3),
                matched_anchor=best_anchor_text,
            )
            return RouterDecision(
                intent=best_intent,
                reasoning=(
                    f"语义相似度匹配成功 (置信度 {best_score:.2f} >= {self.similarity_threshold:.2f})，"
                    f"与典型样本「{best_anchor_text[:16]}...」语义相符，规划为【{best_intent.value}】模式。"
                ),
            )

        # --- Level 3: Safe Fallback to SOLVE ---
        logger.info("router_fallback_to_solve", message_len=len(raw_text))
        return RouterDecision(
            intent=MathIntent.SOLVE,
            reasoning="未检测到特殊前缀或偏向性规则，安全降级为通用性最高的【综合求解 (solve)】模式。",
        )


router_service = RouterService()
