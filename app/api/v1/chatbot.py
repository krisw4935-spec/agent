"""Chatbot API endpoints for handling chat interactions.

This module provides endpoints for chat interactions, including regular chat,
streaming chat, message history management, and chat history clearing.
"""

import asyncio
import json

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import StreamingResponse

from app.api.v1.auth import get_current_session
from app.core.config import settings
from app.core.langgraph.graph import LangGraphAgent
from app.core.limiter import limiter
from app.core.logging import logger
from app.core.metrics import llm_stream_duration_seconds
from app.models.session import Session
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    StreamResponse,
)
from app.services.session_naming import maybe_name_session

router = APIRouter()
agent = LangGraphAgent()


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat"][0])
async def chat(
    request: Request,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
):
    """Process a chat request using LangGraph.

    Args:
        request: The FastAPI request object for rate limiting.
        chat_request: The chat request containing messages.
        session: The current session from the auth token.

    Returns:
        ChatResponse: The processed chat response.

    Raises:
        HTTPException: If there's an error processing the request.
    """
    try:
        logger.info(
            "chat_request_received",
            session_id=session.id,
            message_count=len(chat_request.messages),
        )

        if settings.SESSION_NAMING_ENABLED:
            maybe_name_session(session.id, session.name, chat_request.messages)

        result = await agent.get_response(
            chat_request.messages, session.id, user_id=str(session.user_id), username=session.username
        )

        logger.info("chat_request_processed", session_id=session.id)

        return ChatResponse(messages=result)
    except Exception as e:
        logger.exception("chat_request_failed", session_id=session.id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat_stream"][0])
async def chat_stream(
    request: Request,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
):
    """Process a chat request using LangGraph with streaming response.

    Args:
        request: The FastAPI request object for rate limiting.
        chat_request: The chat request containing messages.
        session: The current session from the auth token.

    Returns:
        StreamingResponse: A streaming response of the chat completion.

    Raises:
        HTTPException: If there's an error processing the request.
    """
    try:
        logger.info(
            "stream_chat_request_received",
            session_id=session.id,
            message_count=len(chat_request.messages),
        )

        if settings.SESSION_NAMING_ENABLED:
            maybe_name_session(session.id, session.name, chat_request.messages)

        async def event_generator():
            """Generate streaming events.

            Yields:
                str: Server-sent events in JSON format.

            Raises:
                Exception: If there's an error during streaming.
            """
            try:
                with llm_stream_duration_seconds.labels(model=agent.llm_service.get_llm().get_name()).time():
                    was_interrupted = False
                    async for event in agent.get_stream_response(
                        chat_request.messages, session.id, user_id=str(session.user_id), username=session.username
                    ):
                        if await request.is_disconnected():
                            logger.info("client_disconnected_aborting_stream", session_id=session.id)
                            break

                        if isinstance(event, dict):
                            if event.get("interrupted"):
                                was_interrupted = True
                            response = StreamResponse(
                                content=event.get("content", ""),
                                thinking=event.get("thinking", ""),
                                status=event.get("status", ""),
                                tool_name=event.get("tool_name", ""),
                                tool_args=event.get("tool_args", ""),
                                tool_output=event.get("tool_output", ""),
                                interrupted=bool(event.get("interrupted", False)),
                                interrupt_question=str(event.get("interrupt_question", "") or ""),
                                done=False,
                            )
                        else:
                            response = StreamResponse(content=str(event), done=False)
                        yield f"data: {json.dumps(response.model_dump(mode='json'))}\n\n"

                # Send final message indicating completion if still connected
                if not await request.is_disconnected():
                    final_response = StreamResponse(
                        content="",
                        done=True,
                        interrupted=was_interrupted,
                    )
                    yield f"data: {json.dumps(final_response.model_dump(mode='json'))}\n\n"

            except asyncio.CancelledError:
                logger.info("stream_chat_client_cancelled", session_id=session.id)
                return

            except Exception as e:
                logger.exception(
                    "stream_chat_request_failed",
                    session_id=session.id,
                    error=str(e),
                )
                err_str = str(e)
                is_429 = "429" in err_str or "rate limit" in err_str.lower() or "tpm" in err_str.lower() or "rpm" in err_str.lower()
                if is_429:
                    error_msg = (
                        f"\n\n---\n⚠️ **请求遭遇上游模型 429 速率限制错误 (Rate Limit Exceeded)**\n\n"
                        f"上游大模型服务商并发或每分钟 Token 额度 (TPM/RPM) 暂时耗尽。\n\n"
                        f"**详细异常信息**:\n```\n{err_str}\n```\n\n"
                        f"**建议**：请等待约 30~60 秒后再发送请求。"
                    )
                else:
                    error_msg = f"\n\n---\n❌ **生成过程中断**: {err_str}"
                error_response = StreamResponse(content=error_msg, done=True)
                yield f"data: {json.dumps(error_response.model_dump(mode='json'))}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except Exception as e:
        logger.exception(
            "stream_chat_request_failed",
            session_id=session.id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/messages", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["messages"][0])
async def get_session_messages(
    request: Request,
    session: Session = Depends(get_current_session),
):
    """Get all messages for a session.

    Args:
        request: The FastAPI request object for rate limiting.
        session: The current session from the auth token.

    Returns:
        ChatResponse: All messages in the session.

    Raises:
        HTTPException: If there's an error retrieving the messages.
    """
    try:
        messages = await agent.get_chat_history(session.id)
        return ChatResponse(messages=messages)
    except Exception as e:
        logger.exception("get_messages_failed", session_id=session.id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/messages")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["messages"][0])
async def clear_chat_history(
    request: Request,
    session: Session = Depends(get_current_session),
):
    """Clear all messages for a session.

    Args:
        request: The FastAPI request object for rate limiting.
        session: The current session from the auth token.

    Returns:
        dict: A message indicating the chat history was cleared.
    """
    try:
        await agent.clear_chat_history(session.id)
        return {"message": "Chat history cleared successfully"}
    except Exception as e:
        logger.exception("clear_chat_history_failed", session_id=session.id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
