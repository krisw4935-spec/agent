"""Tests for manual conversation interruption and resumption."""

import asyncio

from app.core.config import settings
from app.core.langgraph.graph import (
    LangGraphAgent,
    _interrupt_message,
    _interrupt_stream_event,
)
from app.schemas.chat import (
    InterruptResponse,
    ResumeRequest,
)


def test_interrupt_and_resume_schemas():
    """Verify InterruptResponse and ResumeRequest schema creation and defaults."""
    resp = InterruptResponse(
        success=True,
        message="Session interrupted successfully",
        session_id="test-session-123",
    )
    assert resp.success is True
    assert resp.session_id == "test-session-123"

    req = ResumeRequest(prompt="请继续推导第三步")
    assert req.prompt == "请继续推导第三步"

    req_default = ResumeRequest()
    assert req_default.prompt == ""


def test_interrupt_message_and_stream_event_helpers():
    """Verify _interrupt_message and _interrupt_stream_event for manual and auto interrupts."""
    auto_msg = _interrupt_message("请确认解法", manual=False)
    assert auto_msg.interrupted is True
    assert auto_msg.manual_interrupted is False
    assert auto_msg.interrupt_question == "请确认解法"

    manual_msg = _interrupt_message("用户手动中断", manual=True)
    assert manual_msg.interrupted is True
    assert manual_msg.manual_interrupted is True

    auto_event = _interrupt_stream_event("请确认解法", manual=False)
    assert auto_event["interrupted"] is True
    assert auto_event["manual_interrupted"] is False
    assert auto_event["tool_name"] == "ask_human"

    manual_event = _interrupt_stream_event("用户手动中断", manual=True)
    assert manual_event["interrupted"] is True
    assert manual_event["manual_interrupted"] is True
    assert manual_event["tool_name"] == "manual_interrupt"
    assert "手动中断" in manual_event["status"]


def test_agent_task_registration_and_interrupt():
    """Verify task registration, cancellation on interrupt, and cleanup."""

    async def _run():
        agent = LangGraphAgent()
        session_id = "test-active-session-001"

        async def long_running_coro():
            await asyncio.sleep(10)

        task = asyncio.create_task(long_running_coro())
        agent.register_task(session_id, task)

        assert session_id in agent._active_tasks
        assert task in agent._active_tasks[session_id]

        # Test manual interrupt
        interrupted = agent.interrupt_session(session_id)
        assert interrupted is True
        assert task.cancelling() > 0
        assert agent.is_session_interrupted(session_id) is True

        # Allow cancellation to process
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert task.cancelled() is True

        # Verify task was unregistered
        assert session_id not in agent._active_tasks

        # Clear interrupt flag
        agent.clear_session_interrupted(session_id)
        assert agent.is_session_interrupted(session_id) is False

    asyncio.run(_run())


def test_agent_interrupt_no_active_tasks():
    """Verify interrupt on a session without active tasks returns False but marks session."""
    agent = LangGraphAgent()
    session_id = "idle-session-002"

    interrupted = agent.interrupt_session(session_id)
    assert interrupted is False
    assert agent.is_session_interrupted(session_id) is True


def test_rate_limit_endpoints_contain_interrupt_and_resume():
    """Verify rate limit configurations include interrupt and resume endpoints."""
    assert "interrupt" in settings.RATE_LIMIT_ENDPOINTS
    assert "resume" in settings.RATE_LIMIT_ENDPOINTS
