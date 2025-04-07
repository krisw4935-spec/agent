"""Convert checkpoint message lists into API Message turns with tool segments."""

import json
import re
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)

from app.core.langgraph.helpers import get_friendly_tool_name
from app.schemas import (
    Message,
    MessageSegment,
    ToolCallInfo,
)
from app.utils import extract_text_content


def process_graph_messages(messages: list[Any]) -> list[Message]:
    """Convert raw graph checkpoint messages into structured conversation turns.

    Preserves the exact chronological order in which reasoning, text output,
    and function/tool calls occurred during execution.
    """
    result: list[Message] = []

    turn_segments: list[MessageSegment] = []
    tool_call_segments_by_id: dict[str, MessageSegment] = {}
    in_assistant_turn: bool = False

    def flush_assistant_turn():
        nonlocal turn_segments, tool_call_segments_by_id, in_assistant_turn
        if not in_assistant_turn:
            return

        if turn_segments:
            thinking_text = "\n\n".join(
                seg.content for seg in turn_segments if seg.type == "thinking" and seg.content
            ).strip()
            final_content = "\n\n".join(
                seg.content for seg in turn_segments if seg.type == "text" and seg.content
            ).strip()
            tool_calls_list = [
                ToolCallInfo(
                    tool_name=s.tool_name,
                    tool_args=s.tool_args,
                    tool_output=s.tool_output,
                    status=s.status,
                )
                for s in turn_segments
                if s.type == "tool_call"
            ]

            result.append(
                Message(
                    role="assistant",
                    content=final_content,
                    thinking=thinking_text,
                    tool_calls=tool_calls_list,
                    segments=turn_segments,
                )
            )

        turn_segments = []
        tool_call_segments_by_id = {}
        in_assistant_turn = False

    def _get_msg_content(item: Any) -> Any:
        if isinstance(item, dict):
            return item.get("content", "")
        return getattr(item, "content", "")

    def _get_msg_reasoning(item: Any) -> str:
        if isinstance(item, dict):
            return str(item.get("reasoning_content") or item.get("thinking") or "")
        add_kw = getattr(item, "additional_kwargs", None)
        if isinstance(add_kw, dict):
            val = add_kw.get("reasoning_content") or add_kw.get("reasoning")
            if val:
                return str(val)
        resp_meta = getattr(item, "response_metadata", None)
        if isinstance(resp_meta, dict):
            val = resp_meta.get("reasoning_content") or resp_meta.get("reasoning")
            if val:
                return str(val)
        direct = getattr(item, "reasoning_content", None)
        return str(direct) if direct else ""

    def _get_msg_tool_calls(item: Any) -> list[Any]:
        if isinstance(item, dict):
            tc = item.get("tool_calls")
            return tc if isinstance(tc, list) else []
        tc = getattr(item, "tool_calls", None)
        if isinstance(tc, list) and tc:
            return tc
        add_kw = getattr(item, "additional_kwargs", None)
        if isinstance(add_kw, dict):
            tc_kw = add_kw.get("tool_calls")
            if isinstance(tc_kw, list):
                return tc_kw
        return []

    for msg in messages:
        role = ""
        if isinstance(msg, HumanMessage) or (isinstance(msg, BaseMessage) and msg.type == "human"):
            role = "user"
        elif isinstance(msg, AIMessage) or (isinstance(msg, BaseMessage) and msg.type == "ai"):
            role = "assistant"
        elif isinstance(msg, ToolMessage) or (isinstance(msg, BaseMessage) and msg.type == "tool"):
            role = "tool"
        elif isinstance(msg, Message):
            role = msg.role
        elif isinstance(msg, dict):
            raw_role = str(msg.get("role") or msg.get("type") or "")
            if raw_role in ("human", "user"):
                role = "user"
            elif raw_role in ("ai", "assistant"):
                role = "assistant"
            elif raw_role in ("tool", "function"):
                role = "tool"

        if role == "user":
            flush_assistant_turn()
            raw_user_content = _get_msg_content(msg)
            content = extract_text_content(raw_user_content)
            if content:
                result.append(Message(role="user", content=content))

        elif role == "assistant":
            in_assistant_turn = True

            reasoning = _get_msg_reasoning(msg)
            if reasoning and reasoning.strip():
                r_text = reasoning.strip()
                if turn_segments and turn_segments[-1].type == "thinking":
                    turn_segments[-1].content = f"{turn_segments[-1].content}\n\n{r_text}".strip()
                else:
                    turn_segments.append(MessageSegment(type="thinking", content=r_text))

            raw_content = _get_msg_content(msg)
            text = extract_text_content(raw_content)
            if "<think>" in text:
                think_matches = re.findall(r"<think>(.*?)(?:</think>|$)", text, re.DOTALL)
                extracted_think = "\n\n".join(m.strip() for m in think_matches if m.strip())
                if extracted_think:
                    if turn_segments and turn_segments[-1].type == "thinking":
                        turn_segments[-1].content = (
                            f"{turn_segments[-1].content}\n\n{extracted_think}".strip()
                        )
                    else:
                        turn_segments.append(MessageSegment(type="thinking", content=extracted_think))
                clean_text = re.sub(r"<think>.*?(?:</think>|$)", "", text, flags=re.DOTALL).strip()
            else:
                clean_text = text.strip()

            if clean_text:
                if turn_segments and turn_segments[-1].type == "text":
                    turn_segments[-1].content = f"{turn_segments[-1].content}\n\n{clean_text}".strip()
                else:
                    turn_segments.append(MessageSegment(type="text", content=clean_text))

            raw_tool_calls = _get_msg_tool_calls(msg)
            if raw_tool_calls:
                for tc in raw_tool_calls:
                    if isinstance(tc, dict):
                        tc_id = str(tc.get("id") or tc.get("tool_call_id") or "")
                        func = tc.get("function") if isinstance(tc.get("function"), dict) else None
                        tc_name = str((func.get("name") if func else tc.get("name")) or "")
                        tc_args_raw = (func.get("arguments") if func else tc.get("args")) or ""
                        if isinstance(tc_args_raw, (dict, list)):
                            tc_args = json.dumps(tc_args_raw, ensure_ascii=False, indent=2)
                        else:
                            tc_args = str(tc_args_raw or "")
                    else:
                        tc_id = str(getattr(tc, "id", "") or getattr(tc, "tool_call_id", ""))
                        tc_name = str(getattr(tc, "name", ""))
                        tc_args_raw = getattr(tc, "args", "")
                        if isinstance(tc_args_raw, (dict, list)):
                            tc_args = json.dumps(tc_args_raw, ensure_ascii=False, indent=2)
                        else:
                            tc_args = str(tc_args_raw or "")

                    friendly = get_friendly_tool_name(tc_name)
                    seg = MessageSegment(
                        type="tool_call",
                        tool_name=tc_name,
                        tool_args=tc_args,
                        tool_output="",
                        status=f"✅ 已完成 {friendly}",
                    )
                    turn_segments.append(seg)
                    if tc_id:
                        tool_call_segments_by_id[tc_id] = seg

        elif role == "tool":
            in_assistant_turn = True
            tc_id = str(
                getattr(msg, "tool_call_id", "")
                or (msg.get("tool_call_id", "") if isinstance(msg, dict) else "")
            )
            tool_name = str(
                getattr(msg, "name", "") or (msg.get("name", "") if isinstance(msg, dict) else "")
            )
            tool_output = str(_get_msg_content(msg))

            if tc_id and tc_id in tool_call_segments_by_id:
                tool_call_segments_by_id[tc_id].tool_output = tool_output
                if not tool_call_segments_by_id[tc_id].tool_name and tool_name:
                    tool_call_segments_by_id[tc_id].tool_name = tool_name
                    tool_call_segments_by_id[tc_id].status = (
                        f"✅ 已完成 {get_friendly_tool_name(tool_name)}"
                    )
            else:
                matched = False
                if tool_name:
                    for seg in turn_segments:
                        if seg.type == "tool_call" and seg.tool_name == tool_name and not seg.tool_output:
                            seg.tool_output = tool_output
                            matched = True
                            break
                if not matched:
                    friendly = get_friendly_tool_name(tool_name)
                    seg = MessageSegment(
                        type="tool_call",
                        tool_name=tool_name,
                        tool_args="",
                        tool_output=tool_output,
                        status=f"✅ 已完成 {friendly}",
                    )
                    turn_segments.append(seg)
                    if tc_id:
                        tool_call_segments_by_id[tc_id] = seg

            imgs = re.findall(r"!\[[^\]]*\]\([^\)]+\)", tool_output)
            if imgs:
                tool_img_content = "\n\n" + "\n\n".join(imgs) + "\n\n"
                turn_segments.append(MessageSegment(type="text", content=tool_img_content))

    flush_assistant_turn()
    return result
