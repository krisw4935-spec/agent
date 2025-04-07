"""LangGraph agent facade: pool, compile, invoke, and stream."""

import asyncio
import json
import re
from typing import (
    Any,
    AsyncGenerator,
    Optional,
    cast,
)
from urllib.parse import quote_plus

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    convert_to_openai_messages,
)
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.errors import GraphInterrupt
from langgraph.graph.state import (
    Command,
    CompiledStateGraph,
)
from langgraph.types import StateSnapshot
from psycopg import (
    AsyncConnection,
    sql,
)
from psycopg.rows import (
    DictRow,
    dict_row,
)
from psycopg_pool import AsyncConnectionPool
from langchain_core.runnables.config import RunnableConfig

from app.core.config import settings
from app.core.langgraph.graph_builder import build_math_tutor_graph
from app.core.langgraph.helpers import (
    degrade_tutor_tool_loop,
    get_friendly_tool_name,
    get_last_user_content,
    is_rate_limit_error,
)
from app.core.langgraph.message_processor import process_graph_messages
from app.core.langgraph.models import (
    NODE_STATUS_MESSAGES,
    TOOL_STATUS_MESSAGES,
    CriticDecision,
)
from app.core.langgraph.nodes import (
    make_critic_node,
    make_router_node,
    make_tutor_node_handlers,
)
from app.core.langgraph.tools import tools
from app.core.logging import logger
from app.core.observability import langfuse_callback_handler, langfuse_trace_context
from app.schemas import Message
from app.services.evolution import evolution_service
from app.services.llm import llm_service
from app.services.memory import memory_service
from app.utils import dump_messages, extract_text_content

# Backward-compatible re-exports for tests and external imports.
_degrade_tutor_tool_loop = degrade_tutor_tool_loop
_get_friendly_tool_name = get_friendly_tool_name
_is_rate_limit_error = is_rate_limit_error

PostgresConnPool = AsyncConnectionPool[AsyncConnection[DictRow]]


class LangGraphAgent:
    """Manages the LangGraph math-tutor workflow and LLM interactions."""

    def __init__(self):
        """Initialize the LangGraph Agent with necessary components."""
        self.llm_service = llm_service
        self.llm_service.bind_tools(tools)
        self.tools_by_name = {tool.name: tool for tool in tools}
        self._connection_pool: Optional[PostgresConnPool] = None
        self._graph: Optional[CompiledStateGraph] = None
        logger.info(
            "langgraph_agent_initialized",
            model=settings.DEFAULT_LLM_MODEL,
            environment=settings.ENVIRONMENT.value,
        )

    async def _get_connection_pool(self) -> PostgresConnPool:
        """Get a PostgreSQL connection pool using environment-specific settings."""
        if self._connection_pool is None:
            try:
                max_size = settings.POSTGRES_POOL_SIZE
                connection_url = (
                    "postgresql://"
                    f"{quote_plus(settings.POSTGRES_USER)}:{quote_plus(settings.POSTGRES_PASSWORD)}"
                    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
                )
                self._connection_pool = AsyncConnectionPool(
                    connection_url,
                    open=False,
                    max_size=max_size,
                    kwargs={
                        "autocommit": True,
                        "connect_timeout": 5,
                        "prepare_threshold": None,
                        "row_factory": dict_row,
                    },
                )
                await self._connection_pool.open()
                logger.info("connection_pool_created", max_size=max_size, environment=settings.ENVIRONMENT.value)
            except Exception as e:
                logger.exception(
                    "connection_pool_creation_failed", error=str(e), environment=settings.ENVIRONMENT.value
                )
                raise e
        return self._connection_pool

    async def create_graph(self) -> CompiledStateGraph:
        """Create and configure the LangGraph workflow with a Postgres checkpointer."""
        if self._graph is None:
            try:
                tutors = make_tutor_node_handlers()
                handlers = {
                    "router": make_router_node(),
                    **tutors,
                    "critic": make_critic_node(),
                }
                graph_builder = build_math_tutor_graph(handlers)

                connection_pool = await self._get_connection_pool()
                checkpointer = AsyncPostgresSaver(connection_pool)
                await checkpointer.setup()

                self._graph = graph_builder.compile(
                    checkpointer=checkpointer,
                    name=f"{settings.PROJECT_NAME} Agent ({settings.ENVIRONMENT.value})",
                )

                logger.info(
                    "graph_created",
                    graph_name=f"{settings.PROJECT_NAME} Agent",
                    environment=settings.ENVIRONMENT.value,
                    has_checkpointer=True,
                )
            except Exception as e:
                logger.exception("graph_creation_failed", error=str(e), environment=settings.ENVIRONMENT.value)
                raise e

        return self._graph

    async def _get_graph(self) -> CompiledStateGraph:
        """Return the compiled graph, creating it on first access."""
        if self._graph is None:
            self._graph = await self.create_graph()
        return self._graph

    def _build_runnable_config(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
    ) -> RunnableConfig:
        """Build LangGraph config with Langfuse callbacks and session metadata."""
        callbacks: list[BaseCallbackHandler] = [langfuse_callback_handler] if settings.LANGFUSE_TRACING_ENABLED else []
        return {
            "configurable": {"thread_id": session_id},
            "callbacks": callbacks,
            "metadata": {
                "langfuse_session_id": session_id,
                "langfuse_user_id": user_id or "anonymous",
                "user_id": user_id,
                "username": username,
                "session_id": session_id,
                "environment": settings.ENVIRONMENT.value,
                "debug": settings.DEBUG,
            },
        }

    async def get_response(
        self,
        messages: list[Message],
        session_id: str,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
    ) -> list[Message]:
        """Get a response from the LLM."""
        graph = await self._get_graph()
        config = self._build_runnable_config(session_id, user_id, username)

        try:
            state, relevant_memory, evolved_lessons = await asyncio.gather(
                graph.aget_state(config),
                memory_service.search(user_id, messages[-1].content),
                evolution_service.search_relevant_reflections(messages[-1].content),
            )

            with langfuse_trace_context(session_id, user_id):
                if state.next:
                    logger.info("resuming_interrupted_graph", session_id=session_id, next_nodes=state.next)
                    response = await graph.ainvoke(
                        Command(resume=messages[-1].content),
                        config=config,
                    )
                else:
                    relevant_memory = relevant_memory or "No relevant memory found."
                    response = await graph.ainvoke(
                        input={
                            "messages": dump_messages(messages),
                            "long_term_memory": relevant_memory,
                            "evolved_lessons": evolved_lessons,
                        },
                        config=config,
                    )

            state = await graph.aget_state(config)
            if state.next:
                interrupt_value = state.tasks[0].interrupts[0].value if state.tasks else "Waiting for input."
                logger.info("graph_interrupted", session_id=session_id, interrupt_value=str(interrupt_value))
                return [Message(role="assistant", content=str(interrupt_value))]

            openai_msgs = cast(list[dict], convert_to_openai_messages(response["messages"]))
            asyncio.create_task(memory_service.add(user_id, openai_msgs, config.get("metadata")))
            return process_graph_messages(response["messages"])
        except GraphInterrupt:
            state = await graph.aget_state(config)
            interrupt_value = state.tasks[0].interrupts[0].value if state.tasks else "Waiting for input."
            logger.info("graph_interrupted", session_id=session_id, interrupt_value=str(interrupt_value))
            return [Message(role="assistant", content=str(interrupt_value))]
        except Exception as e:
            logger.exception("get_response_failed", error=str(e), session_id=session_id)
            raise

    async def get_stream_response(
        self,
        messages: list[Message],
        session_id: str,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
    ) -> AsyncGenerator[dict[str, str], None]:
        """Get a stream response from the LLM with live tool and status visibility."""
        config = self._build_runnable_config(session_id, user_id, username)
        graph = await self._get_graph()

        try:
            state, relevant_memory, evolved_lessons = await asyncio.gather(
                graph.aget_state(config),
                memory_service.search(user_id, messages[-1].content),
                evolution_service.search_relevant_reflections(messages[-1].content),
            )

            with langfuse_trace_context(session_id, user_id):
                if state.next:
                    logger.info("resuming_interrupted_graph_stream", session_id=session_id, next_nodes=state.next)
                    graph_input = Command(resume=messages[-1].content)
                else:
                    relevant_memory = relevant_memory or "No relevant memory found."
                    graph_input = {
                        "messages": dump_messages(messages),
                        "long_term_memory": relevant_memory,
                        "evolved_lessons": evolved_lessons,
                    }

                yield {"status": "🔍 正在分析题目意图与解题策略...", "content": "", "tool_name": ""}

                async for event in graph.astream_events(
                    graph_input,
                    config,
                    version="v2",
                ):
                    event_type = event.get("event")
                    event_name = event.get("name", "")

                    if event_type == "on_tool_start":
                        status_msg = TOOL_STATUS_MESSAGES.get(event_name, f"⚡ 正在调用工具 {event_name}...")
                        raw_input = event.get("data", {}).get("input", {})
                        tool_args_str = (
                            json.dumps(raw_input, ensure_ascii=False, indent=2)
                            if isinstance(raw_input, dict)
                            else str(raw_input or "")
                        )
                        yield {
                            "status": status_msg,
                            "content": "",
                            "tool_name": event_name,
                            "tool_args": tool_args_str,
                            "tool_output": "",
                        }

                    elif event_type == "on_tool_end":
                        output_data = event.get("data", {}).get("output")
                        tool_img_content = ""
                        out_str = ""
                        if output_data:
                            out_str = output_data.content if hasattr(output_data, "content") else str(output_data)
                            imgs = re.findall(r"!\[[^\]]*\]\([^\)]+\)", out_str)
                            if imgs:
                                tool_img_content = "\n\n" + "\n\n".join(imgs) + "\n\n"
                        yield {
                            "status": f"✅ {event_name} 运算完成",
                            "content": tool_img_content,
                            "tool_name": event_name,
                            "tool_args": "",
                            "tool_output": out_str,
                        }

                    elif event_type == "on_chain_start" and event_name in NODE_STATUS_MESSAGES:
                        if event_name == "router":
                            yield {
                                "status": "🔍 正在分析题目意图与解题策略规划...",
                                "content": "",
                                "tool_name": "router_decision",
                                "tool_args": get_last_user_content(messages),
                                "tool_output": "",
                            }
                        elif event_name == "critic":
                            yield {
                                "status": "🕵️ 正在进行 Critic 双智能体逻辑与边界质检...",
                                "content": "",
                                "tool_name": "critic_review",
                                "tool_args": "正在审校当前解题推导严谨性、边界条件、无代码泄漏及教学启发性...",
                                "tool_output": "",
                            }
                        else:
                            yield {"status": NODE_STATUS_MESSAGES[event_name], "content": "", "tool_name": ""}

                    elif event_type == "on_chain_end" and event_name in ("router", "critic"):
                        output_data = event.get("data", {}).get("output")
                        node_output = ""
                        if isinstance(output_data, Command) and isinstance(output_data.update, dict):
                            msgs = output_data.update.get("messages", [])
                            if msgs and hasattr(msgs[0], "content"):
                                node_output = str(msgs[0].content)
                        elif isinstance(output_data, dict):
                            msgs = output_data.get("messages", [])
                            if msgs and hasattr(msgs[0], "content"):
                                node_output = str(msgs[0].content)

                        if event_name == "router":
                            yield {
                                "status": "✅ 意图路由与策略规划完成",
                                "content": "",
                                "tool_name": "router_decision",
                                "tool_args": get_last_user_content(messages),
                                "tool_output": node_output,
                            }
                        elif event_name == "critic":
                            yield {
                                "status": "✅ 已完成 Critic 双智能体审校",
                                "content": "",
                                "tool_name": "critic_review",
                                "tool_args": "针对 6 项审校标准的逐条质检审校",
                                "tool_output": node_output,
                            }

                    elif event_type == "on_chat_model_stream":
                        node_name = event.get("metadata", {}).get("langgraph_node", "")
                        if node_name in ("critic", "router"):
                            continue

                        chunk = event.get("data", {}).get("chunk")
                        if isinstance(chunk, (AIMessage, AIMessageChunk)):
                            reasoning = ""
                            if hasattr(chunk, "additional_kwargs") and isinstance(chunk.additional_kwargs, dict):
                                reasoning = (
                                    chunk.additional_kwargs.get("reasoning_content")
                                    or chunk.additional_kwargs.get("reasoning")
                                    or ""
                                )
                            chunk_any = cast(Any, chunk)
                            if not reasoning and hasattr(chunk_any, "reasoning_content"):
                                reasoning = chunk_any.reasoning_content or ""

                            if reasoning:
                                yield {"status": "", "content": "", "thinking": str(reasoning), "tool_name": ""}

                            if chunk.content:
                                text = extract_text_content(chunk.content)
                                if text:
                                    yield {"status": "", "content": text, "thinking": "", "tool_name": ""}

            state = await graph.aget_state(config)
            if state.next:
                interrupt_value = state.tasks[0].interrupts[0].value if state.tasks else "Waiting for input."
                logger.info("graph_interrupted_stream", session_id=session_id, interrupt_value=str(interrupt_value))
                yield {"status": "", "content": str(interrupt_value), "tool_name": ""}
            elif state.values and "messages" in state.values:
                openai_msgs = cast(list[dict], convert_to_openai_messages(state.values["messages"]))
                asyncio.create_task(memory_service.add(user_id, openai_msgs, config.get("metadata")))
        except GraphInterrupt:
            state = await graph.aget_state(config)
            interrupt_value = state.tasks[0].interrupts[0].value if state.tasks else "Waiting for input."
            logger.info("graph_interrupted_stream", session_id=session_id, interrupt_value=str(interrupt_value))
            yield {"status": "", "content": str(interrupt_value), "tool_name": ""}
        except Exception as stream_error:
            logger.exception("stream_processing_failed", error=str(stream_error), session_id=session_id)
            raise stream_error

    async def get_chat_history(self, session_id: str) -> list[Message]:
        """Get the chat history for a given thread ID."""
        graph = await self._get_graph()
        config: RunnableConfig = {"configurable": {"thread_id": session_id}}
        state: StateSnapshot = await graph.aget_state(config=config)
        return process_graph_messages(state.values["messages"]) if state.values else []

    async def clear_chat_history(self, session_id: str) -> None:
        """Clear all chat history for a given thread ID."""
        try:
            conn_pool = await self._get_connection_pool()
            if conn_pool is None:
                raise RuntimeError("connection pool unavailable; cannot clear chat history")

            async with conn_pool.connection() as conn:
                async with conn.pipeline():
                    for table in settings.CHECKPOINT_TABLES:
                        await conn.execute(
                            sql.SQL("DELETE FROM {} WHERE thread_id = %s").format(sql.Identifier(table)),
                            (session_id,),
                        )
                logger.info(
                    "checkpoint_tables_cleared_for_session",
                    tables=settings.CHECKPOINT_TABLES,
                    session_id=session_id,
                )
        except Exception as e:
            logger.error(
                "clear_chat_history_operation_failed",
                session_id=session_id,
                error=str(e),
            )
            raise


__all__ = [
    "CriticDecision",
    "LangGraphAgent",
    "_degrade_tutor_tool_loop",
    "_get_friendly_tool_name",
    "_is_rate_limit_error",
]
