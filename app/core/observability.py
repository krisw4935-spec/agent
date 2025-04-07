"""Observability module for the application."""

from langfuse import Langfuse, get_client, propagate_attributes
from langfuse.langchain import CallbackHandler

from app.core.config import settings
from app.core.logging import logger


def langfuse_init():
    """Initialize Langfuse."""
    if not settings.LANGFUSE_TRACING_ENABLED:
        logger.debug("langfuse_tracing_disabled")
        return

    if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
        logger.warning(
            "langfuse_keys_missing",
            hint="Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY, or LANGFUSE_TRACING_ENABLED=false",
        )
        return

    langfuse = Langfuse(
        tracing_enabled=settings.LANGFUSE_TRACING_ENABLED,
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
        environment=settings.ENVIRONMENT.value,
        debug=settings.DEBUG,
    )

    try:
        if langfuse.auth_check():
            logger.info("langfuse_auth_success", host=settings.LANGFUSE_HOST)
        else:
            logger.warning("langfuse_auth_failure", host=settings.LANGFUSE_HOST)
    except Exception:
        logger.exception("langfuse_auth_check_failed", host=settings.LANGFUSE_HOST)


def langfuse_flush():
    """Flush pending Langfuse events (call on shutdown)."""
    if not settings.LANGFUSE_TRACING_ENABLED:
        return
    try:
        get_client().flush()
        logger.debug("langfuse_flush_completed")
    except Exception:
        logger.exception("langfuse_flush_failed")


def get_langfuse_callback_handler() -> CallbackHandler:
    """Create a Langfuse CallbackHandler for tracking LLM interactions.

    Returns:
        CallbackHandler: Configured Langfuse callback handler.
    """
    return CallbackHandler()


def langfuse_trace_context(session_id: str, user_id: str | None = None):
    """Return a Langfuse attribute propagator for grouping traces by session/user."""
    if not settings.LANGFUSE_TRACING_ENABLED:
        from contextlib import nullcontext

        return nullcontext()

    return propagate_attributes(
        session_id=session_id,
        user_id=user_id or "anonymous",
        tags=["math-teacher"],
    )


langfuse_callback_handler = get_langfuse_callback_handler()
