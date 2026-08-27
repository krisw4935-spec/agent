"""This file contains the chat schema for the application."""

import re
from typing import (
    List,
    Literal,
)

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)

from app.schemas.base import BaseResponse


class ToolCallInfo(BaseModel):
    """Tool execution detail model.

    Attributes:
        tool_name: The name of the tool called.
        tool_args: Input arguments of the tool call.
        tool_output: Execution output or result of the tool call.
        status: Execution status description.
    """

    model_config = {"extra": "ignore"}

    tool_name: str = Field(default="", description="The name of the tool called")
    tool_args: str = Field(default="", description="Input arguments of the tool call")
    tool_output: str = Field(default="", description="Execution output or result of the tool call")
    status: str = Field(default="", description="Execution status description")


class MessageSegment(BaseModel):
    """A segment block within a message in chronological order.

    Attributes:
        type: Segment type ('thinking', 'tool_call', 'text').
        content: Text content for 'thinking' or 'text' segments.
        tool_name: Name of the tool for 'tool_call' segment.
        tool_args: Input arguments for 'tool_call' segment.
        tool_output: Execution result for 'tool_call' segment.
        status: Status text for 'tool_call' segment.
    """

    model_config = {"extra": "ignore"}

    type: Literal["thinking", "tool_call", "text"] = Field(..., description="Segment type")
    content: str = Field(default="", description="Text or thinking content")
    tool_name: str = Field(default="", description="Tool name if tool_call")
    tool_args: str = Field(default="", description="Tool arguments if tool_call")
    tool_output: str = Field(default="", description="Tool output if tool_call")
    status: str = Field(default="", description="Tool status description")


class Message(BaseModel):
    """Message model for chat endpoint.

    Attributes:
        role: The role of the message sender (user, assistant, system).
        content: The content of the message.
        thinking: Thinking or reasoning process of the model.
        tool_calls: List of tool calls executed during this message turn.
        segments: Chronological list of message segments (thinking, text, tool_call).
        interrupted: Whether the graph is paused waiting for human input.
        interrupt_question: The question posed when interrupted.
    """

    model_config = {"extra": "ignore"}

    role: Literal["user", "assistant", "system"] = Field(..., description="The role of the message sender")
    content: str = Field(default="", description="The content of the message")
    thinking: str = Field(default="", description="Thinking or reasoning process of the model")
    tool_calls: List[ToolCallInfo] = Field(default_factory=list, description="Tool calls executed during this turn")
    segments: List[MessageSegment] = Field(
        default_factory=list, description="Chronological segments of the message"
    )
    interrupted: bool = Field(default=False, description="Whether the graph is paused waiting for human input")
    interrupt_question: str = Field(default="", description="The question posed when interrupted")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate the message content.

        Args:
            v: The content to validate

        Returns:
            str: The validated content

        Raises:
            ValueError: If the content contains disallowed patterns
        """
        if not v:
            return ""

        # Check for potentially harmful content
        if re.search(r"<script.*?>.*?</script>", v, re.IGNORECASE | re.DOTALL):
            raise ValueError("Content contains potentially harmful script tags")

        # Check for null bytes
        if "\0" in v:
            raise ValueError("Content contains null bytes")

        return v


class ChatRequest(BaseModel):
    """Request model for chat endpoint.

    Attributes:
        messages: List of messages in the conversation.
    """

    messages: List[Message] = Field(
        ...,
        description="List of messages in the conversation",
        min_length=1,
    )


class ChatResponse(BaseResponse):
    """Response model for chat endpoint.

    Attributes:
        messages: List of messages in the conversation.
    """

    messages: List[Message] = Field(..., description="List of messages in the conversation")


class StreamResponse(BaseResponse):
    """Response model for streaming chat endpoint.

    Attributes:
        content: The content of the current chunk.
        thinking: The thinking or reasoning tokens of the chunk.
        status: Current agent state or tool execution status description.
        tool_name: Name of the tool currently being called.
        done: Whether the stream is complete.
        interrupted: Whether the graph is paused waiting for human input.
        interrupt_question: The question posed when interrupted.
    """

    content: str = Field(default="", description="The content of the current chunk")
    thinking: str = Field(default="", description="The thinking or reasoning tokens of the chunk")
    status: str = Field(default="", description="Current agent state or tool execution status description")
    tool_name: str = Field(default="", description="Name of the tool currently being called")
    tool_args: str = Field(default="", description="Input arguments of the tool call")
    tool_output: str = Field(default="", description="Execution output/result of the tool call")
    done: bool = Field(default=False, description="Whether the stream is complete")
    interrupted: bool = Field(default=False, description="Whether the graph is paused waiting for human input")
    interrupt_question: str = Field(default="", description="The question posed when interrupted")


class SessionTitle(BaseModel):
    """Structured output schema for session title generation."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=60,
    )

    @field_validator("title")
    @classmethod
    def _normalize(cls, v: str) -> str:
        v = " ".join(v.split()).strip(" \"'`.,:;!?-")
        if not v:
            raise ValueError("empty title after normalization")
        return v
