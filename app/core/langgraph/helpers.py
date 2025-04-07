"""Pure helpers shared by LangGraph tutor nodes and message processing."""

from typing import Literal

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
)

from app.core.langgraph.models import FRIENDLY_TOOL_NAMES
from app.schemas import Message
from app.utils import extract_text_content


def get_friendly_tool_name(tool_name: str) -> str:
    """Map tool technical name to user-friendly Chinese description."""
    return FRIENDLY_TOOL_NAMES.get(tool_name, tool_name or "数学工具演算")


def get_last_user_content(messages: list) -> str:
    """Extract the most recent user/human message text from graph state."""
    for msg in reversed(messages):
        if isinstance(msg, Message) and msg.role == "user":
            return msg.content
        if isinstance(msg, BaseMessage) and (msg.type == "human" or getattr(msg, "role", None) == "user"):
            return extract_text_content(msg.content)
        if isinstance(msg, dict) and (msg.get("role") in ("user", "human") or msg.get("type") in ("user", "human")):
            return str(msg.get("content", ""))
    return ""


def normalize_messages(messages: list) -> list[Message]:
    """Convert graph state messages to schema Message objects for prompt prep."""
    normalized: list[Message] = []
    for msg in messages:
        if isinstance(msg, Message):
            normalized.append(msg)
        elif isinstance(msg, BaseMessage):
            role_map: dict[str, Literal["user", "assistant", "system"]] = {
                "human": "user",
                "ai": "assistant",
                "system": "system",
            }
            if msg.type in role_map:
                role = role_map[msg.type]
                content = extract_text_content(msg.content)
                if content:
                    normalized.append(Message(role=role, content=content))
        elif isinstance(msg, dict) and msg.get("content"):
            raw_role = msg.get("role", "user")
            if raw_role in ("user", "human"):
                normalized.append(Message(role="user", content=str(msg["content"])))
            elif raw_role in ("ai", "assistant"):
                normalized.append(Message(role="assistant", content=str(msg["content"])))
            elif raw_role == "system":
                normalized.append(Message(role="system", content=str(msg["content"])))
    return normalized


def is_rate_limit_error(error: Exception) -> bool:
    """Detect SenseNova / OpenAI RPM-TPM exhaustion across error wrappers."""
    text = str(error).lower()
    return any(
        marker in text
        for marker in ("429", "rate limit", "rpm exhausted", "tpm exhausted", "429001")
    )


def degrade_tutor_tool_loop(new_messages: list[BaseMessage], error: Exception) -> AIMessage:
    """Build a usable reply from partial tool-loop progress instead of failing hard."""
    parts: list[str] = []
    for msg in new_messages:
        if isinstance(msg, AIMessage):
            text = extract_text_content(msg.content).strip()
            if text:
                parts.append(text)

    is_429 = is_rate_limit_error(error)
    if parts:
        suffix = (
            f"\n\n---\n⚠️ **（上游模型接口返回 429 速率限制，以上为已完成的推导与验算结果）**\n\n```\n{error}\n```\n若需更深入探讨，请稍后再试。"
            if is_429
            else f"\n\n---\n⚠️ **（后续生成中断: {error}，以上为已完成的推导结果）**"
        )
        return AIMessage(content="\n\n".join(parts) + suffix)

    if is_429:
        return AIMessage(
            content=(
                f"⚠️ **上游模型接口返回 429 速率限制错误 (Rate Limit Exceeded)**\n\n"
                f"上游大模型提供方当前并发或每分钟 Token 配额 (TPM/RPM) 已耗尽。\n\n"
                f"**详细错误信息**:\n```\n{error}\n```\n\n"
                f"**建议**：请等待约 30~60 秒后重试，或检查后端备用模型配置。"
            )
        )
    return AIMessage(content=f"⚠️ 解答生成暂时遇到异常: {error}，请稍后重试。")
