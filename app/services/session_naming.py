"""Session auto-naming feature.

On the first message of a new session this module:
  1. Atomically claims the session in Postgres (prevents duplicate LLM calls
     across concurrent requests and multiple uvicorn workers).
  2. Writes a placeholder name derived from the user's message so the session
     always has a sensible name even if the LLM call later fails.
  3. Fires a background asyncio task that calls a fast nano model with
     structured output to generate a proper title and overwrites the placeholder.
"""

import asyncio
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from sqlmodel import (
    Session as DBSession,
    col,
    update,
)

from app.core.logging import logger
from app.core.metrics import session_names_generated_total
from app.core.prompts import SESSION_TITLE_PROMPT
from app.models.session import Session as ChatSession
from app.schemas.chat import Message, SessionTitle
from app.services.database import database_service
from app.services.llm import llm_service
from app.utils.graph import extract_text_content

_PLACEHOLDER_MAX = 40

_background_tasks: set[asyncio.Task] = set()


def _build_placeholder(user_message: str) -> str:
    cleaned = " ".join(user_message.split())
    return cleaned[:_PLACEHOLDER_MAX].rstrip() or "New chat"


def _claim_session(session_id: str, placeholder: str) -> bool:
    """Return True iff this caller wins the atomic Postgres claim.

    Executes UPDATE … WHERE name = '' in a single round-trip so exactly one
    concurrent caller receives rowcount == 1.
    """
    with DBSession(database_service.engine) as db:
        stmt = (
            update(ChatSession)
            .where(col(ChatSession.id) == session_id, col(ChatSession.name) == "")
            .values(name=placeholder)
        )
        result = db.exec(stmt)
        db.commit()
        return (result.rowcount or 0) == 1


async def _persist_session_name(session_id: str, user_message: str) -> None:
    try:
        result = await llm_service.call(
            [
                SystemMessage(content=SESSION_TITLE_PROMPT),
                HumanMessage(content=user_message[:500]),
            ],
            model_name="gpt-5.4-nano",
            response_format=SessionTitle,
            reasoning={"effort": "low"},
            max_tokens=32,
            temperature=0.3,
        )
        await database_service.update_session_name(session_id, result.title)
        session_names_generated_total.labels(status="success").inc()
        logger.info("session_name_generated", session_id=session_id, name=result.title)
    except Exception:
        session_names_generated_total.labels(status="error").inc()
        logger.exception("session_name_generation_failed", session_id=session_id)


def maybe_name_session(session_id: str, session_name: str, messages: list[Any]) -> None:
    """Trigger session auto-naming if the session is still unnamed.

    Safe to call from any chat endpoint — concurrent callers for the same
    session are deduplicated by the Postgres claim.
    """
    if session_name:
        return
    first_user_msg: str | None = None
    for m in messages:
        if isinstance(m, Message):
            if m.role == "user" and m.content:
                first_user_msg = m.content
                break
        elif isinstance(m, BaseMessage):
            if (m.type == "human" or getattr(m, "role", None) == "user") and m.content:
                first_user_msg = extract_text_content(m.content)
                break
        elif isinstance(m, dict):
            role = m.get("role") or m.get("type")
            if role in ("user", "human") and m.get("content"):
                first_user_msg = str(m.get("content"))
                break
        else:
            role = getattr(m, "role", getattr(m, "type", None))
            content = getattr(m, "content", None)
            if role in ("user", "human") and content:
                first_user_msg = str(content)
                break

    if not first_user_msg:
        return
    if _claim_session(session_id, _build_placeholder(first_user_msg)):
        task = asyncio.create_task(_persist_session_name(session_id, first_user_msg))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
