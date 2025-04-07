"""This file contains the graph utilities for the application."""

from typing import Any, Literal

import tiktoken
from langchain_core.messages import BaseMessage
from langchain_core.messages import trim_messages as _trim_messages

from app.core.config import settings
from app.core.logging import logger
from app.schemas import Message

# Cache tiktoken encoding at module level — thread-safe and reusable
try:
    _TIKTOKEN_ENCODING = tiktoken.encoding_for_model(settings.DEFAULT_LLM_MODEL)
except KeyError:
    _TIKTOKEN_ENCODING = tiktoken.get_encoding("cl100k_base")


def _count_tokens_tiktoken(messages: list) -> int:
    """Count tokens locally using tiktoken — no API call needed."""
    num_tokens = 0
    for message in messages:
        # Every message has overhead tokens for role/name
        num_tokens += 4
        if isinstance(message, dict):
            for _, value in message.items():
                if isinstance(value, str):
                    num_tokens += len(_TIKTOKEN_ENCODING.encode(value))
        elif isinstance(message, BaseMessage):
            content = message.content
            if isinstance(content, str):
                num_tokens += len(_TIKTOKEN_ENCODING.encode(content))
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, str):
                        num_tokens += len(_TIKTOKEN_ENCODING.encode(block))
                    elif isinstance(block, dict) and "text" in block:
                        num_tokens += len(_TIKTOKEN_ENCODING.encode(block["text"]))
    num_tokens += 2  # every reply is primed with assistant
    return num_tokens


def dump_messages(messages: list[Any]) -> list[dict]:
    """Dump the messages to a list of dictionaries for LLM input.

    Args:
        messages (list[Any]): The messages to dump (supports Message, BaseMessage, or dict).

    Returns:
        list[dict]: The dumped messages with role and content.
    """
    dumped: list[dict] = []
    for message in messages:
        if isinstance(message, Message):
            dumped.append({"role": message.role, "content": message.content})
        elif isinstance(message, BaseMessage):
            role_map = {"human": "user", "ai": "assistant", "system": "system", "tool": "tool"}
            role = role_map.get(message.type, getattr(message, "role", "user"))
            dumped.append({"role": role, "content": extract_text_content(message.content)})
        elif isinstance(message, dict):
            raw_role = str(message.get("role") or message.get("type") or "user")
            if raw_role in ("human", "user"):
                role = "user"
            elif raw_role in ("ai", "assistant"):
                role = "assistant"
            elif raw_role in ("tool", "function"):
                role = "tool"
            else:
                role = raw_role
            dumped.append({"role": role, "content": str(message.get("content", ""))})
        else:
            role = getattr(message, "role", getattr(message, "type", "user"))
            if role == "human":
                role = "user"
            elif role == "ai":
                role = "assistant"
            dumped.append({"role": str(role), "content": str(getattr(message, "content", ""))})
    return dumped


def extract_text_content(content: str | list) -> str:
    """Extract plain text from an LLM content value.

    Handles both the simple string format and the structured block list returned
    by GPT-5 / Responses API models:
        [{'type': 'reasoning', ...}, {'type': 'text', 'text': '...'}]

    Args:
        content: Raw content from a LangChain BaseMessage.

    Returns:
        Plain text string (empty string when nothing extractable is present).
    """
    if isinstance(content, str):
        return content

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif block.get("type") == "reasoning":
                logger.debug(
                    "reasoning_block_received",
                    reasoning_id=block.get("id"),
                    has_summary=bool(block.get("summary")),
                )
    return "".join(parts)


def process_llm_response(response: BaseMessage) -> BaseMessage:
    """Normalise a raw LLM response so that ``response.content`` is always a plain string, regardless of the provider's content format.

    Args:
        response: The raw response from the LLM.

    Returns:
        The same BaseMessage instance with ``content`` set to a plain string.
    """
    if isinstance(response.content, list):
        response.content = extract_text_content(response.content)
        logger.debug(
            "processed_structured_content",
            content_block_count=len(response.content),
            extracted_length=len(response.content),
        )
    return response


def prepare_messages(messages: list[Any], system_prompt: str) -> list[Message]:
    """Prepare the messages for the LLM.

    Args:
        messages (list[Any]): The messages to prepare.
        system_prompt (str): The system prompt to use.

    Returns:
        list[Message]: The prepared messages.
    """
    try:
        trimmed_messages = _trim_messages(
            dump_messages(messages),
            strategy="last",
            token_counter=_count_tokens_tiktoken,
            max_tokens=settings.MAX_TOKENS,
            start_on="human",
            include_system=False,
            allow_partial=False,
        )
    except ValueError as e:
        # Handle unrecognized content blocks (e.g., reasoning blocks from GPT-5)
        if "Unrecognized content block type" in str(e):
            logger.warning(
                "token_counting_failed_skipping_trim",
                error=str(e),
                message_count=len(messages),
            )
            # Skip trimming and return all messages
            trimmed_messages = messages
        else:
            raise

    converted: list[Message] = []
    for msg in trimmed_messages:
        if isinstance(msg, Message):
            converted.append(msg)
        elif isinstance(msg, BaseMessage):
            role_map: dict[str, Literal["user", "assistant", "system"]] = {
                "human": "user",
                "ai": "assistant",
                "system": "system",
            }
            role = role_map.get(msg.type, "user")
            converted.append(Message(role=role, content=extract_text_content(msg.content)))
        elif isinstance(msg, dict):
            raw_role = str(msg.get("role") or msg.get("type") or "user")
            role_val: Literal["user", "assistant", "system"] = (
                "user"
                if raw_role in ("human", "user")
                else ("assistant" if raw_role in ("ai", "assistant") else "system")
            )
            converted.append(Message(role=role_val, content=str(msg.get("content", ""))))

    return [Message(role="system", content=system_prompt)] + converted
