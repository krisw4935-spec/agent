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
    InterruptResponse,
    ResumeRequest,
    StreamResponse,
)
from app.services.session_naming import maybe_name_session
from app.services.suggested_questions import generate_suggested_questions

router = APIRouter()
agent = LangGraphAgent()


def _format_sse_event(payload: dict[str, object]) -> str:
    """Serialize a JSON payload as a server-sent event."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


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
            current_task = asyncio.current_task()
            if current_task is not None:
                agent.register_task(session.id, current_task)
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
                                manual_interrupted=bool(event.get("manual_interrupted", False)),
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
                is_429 = (
                    "429" in err_str
                    or "rate limit" in err_str.lower()
                    or "tpm" in err_str.lower()
                    or "rpm" in err_str.lower()
                )
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
            finally:
                if current_task is not None:
                    agent.unregister_task(session.id, current_task)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except Exception as e:
        logger.exception(
            "stream_chat_request_failed",
            session_id=session.id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/interrupt", response_model=InterruptResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["interrupt"][0])
async def interrupt_chat(
    request: Request,
    session: Session = Depends(get_current_session),
):
    """Manually interrupt the active chat generation for the current session.

    Args:
        request: The FastAPI request object for rate limiting.
        session: The current session from the auth token.

    Returns:
        InterruptResponse: Result of the interruption operation.
    """
    try:
        logger.info(
            "interrupt_chat_request_received",
            session_id=session.id,
            user_id=session.user_id,
        )
        interrupted = agent.interrupt_session(session.id)
        return InterruptResponse(
            success=True,
            message="生成已成功中断" if interrupted else "当前会话已记录中断状态",
            session_id=session.id,
        )
    except Exception as e:
        logger.exception("interrupt_chat_request_failed", session_id=session.id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/resume")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["resume"][0])
async def resume_chat(
    request: Request,
    resume_req: ResumeRequest,
    session: Session = Depends(get_current_session),
):
    """Resume an interrupted chat session with streaming response.

    Args:
        request: The FastAPI request object for rate limiting.
        resume_req: The resume request containing optional continuation prompt.
        session: The current session from the auth token.

    Returns:
        StreamingResponse: A streaming response continuing the chat completion.
    """
    try:
        logger.info(
            "stream_resume_chat_request_received",
            session_id=session.id,
            prompt=resume_req.prompt,
        )

        async def event_generator():
            current_task = asyncio.current_task()
            if current_task is not None:
                agent.register_task(session.id, current_task)
            try:
                with llm_stream_duration_seconds.labels(model=agent.llm_service.get_llm().get_name()).time():
                    was_interrupted = False
                    async for event in agent.get_stream_response(
                        messages=[],
                        session_id=session.id,
                        user_id=str(session.user_id),
                        username=session.username,
                        is_resume=True,
                        resume_prompt=resume_req.prompt,
                    ):
                        if await request.is_disconnected():
                            logger.info("client_disconnected_aborting_resume_stream", session_id=session.id)
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
                                manual_interrupted=bool(event.get("manual_interrupted", False)),
                                done=False,
                            )
                        else:
                            response = StreamResponse(content=str(event), done=False)
                        yield f"data: {json.dumps(response.model_dump(mode='json'))}\n\n"

                if not await request.is_disconnected():
                    final_response = StreamResponse(
                        content="",
                        done=True,
                        interrupted=was_interrupted,
                    )
                    yield f"data: {json.dumps(final_response.model_dump(mode='json'))}\n\n"

            except asyncio.CancelledError:
                logger.info("stream_resume_client_cancelled", session_id=session.id)
                return
            except Exception as e:
                logger.exception("stream_resume_request_failed", session_id=session.id, error=str(e))
                err_str = str(e)
                error_response = StreamResponse(content=f"\n\n---\n❌ **恢复过程中断**: {err_str}", done=True)
                yield f"data: {json.dumps(error_response.model_dump(mode='json'))}\n\n"
            finally:
                if current_task is not None:
                    agent.unregister_task(session.id, current_task)

        return StreamingResponse(event_generator(), media_type="text/event-stream")
    except Exception as e:
        logger.exception("stream_resume_failed", session_id=session.id, error=str(e))
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


@router.get("/suggested-questions")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["suggested_questions"][0])
async def get_suggested_questions(
    request: Request,
    session: Session = Depends(get_current_session),
):
    """Stream AI suggested starter questions for the chat greeting over SSE.

    Args:
        request: The FastAPI request object for rate limiting.
        session: The current session from the auth token.

    Returns:
        StreamingResponse: SSE events containing status and recommended questions.
    """
    logger.info(
        "suggested_questions_request_received",
        session_id=session.id,
        user_id=session.user_id,
    )

    async def event_generator():
        """Yield an immediate status event, heartbeats, and the final result."""
        generation_task = asyncio.create_task(
            generate_suggested_questions(
                session_id=session.id,
                user_id=str(session.user_id),
            )
        )
        try:
            yield _format_sse_event({"status": "generating", "done": False})

            while not generation_task.done():
                done, _ = await asyncio.wait({generation_task}, timeout=10)
                if done:
                    break
                if await request.is_disconnected():
                    logger.info("suggested_questions_client_disconnected", session_id=session.id)
                    return
                yield ": keep-alive\n\n"

            if await request.is_disconnected():
                return

            questions = generation_task.result()
            logger.info(
                "suggested_questions_stream_completed",
                session_id=session.id,
                question_count=len(questions),
            )
            yield _format_sse_event(
                {
                    "questions": [question.model_dump(mode="json") for question in questions],
                    "status": "completed",
                    "done": True,
                }
            )
        except asyncio.CancelledError:
            logger.info("suggested_questions_stream_cancelled", session_id=session.id)
            return
        except Exception as e:
            logger.exception("suggested_questions_request_failed", session_id=session.id, error=str(e))
            yield _format_sse_event(
                {
                    "error": "推荐问题生成失败，请稍后重试",
                    "status": "failed",
                    "done": True,
                }
            )
        finally:
            if not generation_task.done():
                generation_task.cancel()
            await asyncio.gather(generation_task, return_exceptions=True)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
