#!/usr/bin/env python3
"""Seed Langfuse traces from standard math teacher cases, then run LLM-judge eval."""

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

import httpx

# Fix import path for app module
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.core.langgraph.graph import LangGraphAgent
from app.core.logging import logger
from app.core.observability import langfuse_flush
from app.schemas.chat import Message
from evals.evaluator import Evaluator

DEFAULT_DATASET = Path(__file__).parent / "datasets" / "math_teacher_cases.json"
DEFAULT_BASE_URL = "http://localhost:8000"
EVAL_PASSWORD = "EvalTest123!"


def load_cases(dataset_path: Path) -> list[dict]:
    """Load regression cases from JSON dataset."""
    with open(dataset_path, encoding="utf-8") as f:
        data = json.load(f)
    cases = data.get("cases", [])
    if not cases:
        raise ValueError(f"No cases found in {dataset_path}")
    return cases


async def run_cases_via_agent(cases: list[dict]) -> None:
    """Invoke LangGraph directly (requires Postgres checkpointer)."""
    agent = LangGraphAgent()
    await agent.create_graph()
    user_id = "eval-regression-user"

    for case in cases:
        session_id = str(uuid.uuid4())
        messages = [Message(role="user", content=case["message"])]
        logger.info(
            "regression_case_started",
            case_id=case["id"],
            expected_intent=case.get("intent"),
            session_id=session_id,
        )
        try:
            result = await agent.get_response(
                messages,
                session_id=session_id,
                user_id=user_id,
                username="eval-student",
            )
            preview = result[-1].content[:120] if result else ""
            logger.info("regression_case_completed", case_id=case["id"], preview=preview)
            print(f"  ✓ {case['id']} ({case.get('intent', '?')})")
        except Exception as e:
            logger.exception("regression_case_failed", case_id=case["id"], error=str(e))
            print(f"  ✗ {case['id']}: {e}")
            raise

    langfuse_flush()


async def run_cases_via_api(cases: list[dict], base_url: str) -> None:
    """Send cases through the HTTP API (requires running server)."""
    email = f"eval-regression-{uuid.uuid4().hex[:8]}@example.com"
    async with httpx.AsyncClient(base_url=base_url, timeout=120.0) as client:
        reg = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": EVAL_PASSWORD, "username": "eval-student"},
        )
        reg.raise_for_status()
        user_token = reg.json()["token"]["access_token"]

        for case in cases:
            sess = await client.post(
                "/api/v1/auth/session",
                headers={"Authorization": f"Bearer {user_token}"},
            )
            sess.raise_for_status()
            session_token = sess.json()["token"]["access_token"]

            logger.info(
                "regression_case_started",
                case_id=case["id"],
                expected_intent=case.get("intent"),
                mode="api",
            )
            chat = await client.post(
                "/api/v1/chatbot/chat",
                headers={"Authorization": f"Bearer {session_token}"},
                json={"messages": [{"role": "user", "content": case["message"]}]},
            )
            chat.raise_for_status()
            messages = chat.json().get("messages", [])
            preview = messages[-1]["content"][:120] if messages else ""
            logger.info("regression_case_completed", case_id=case["id"], preview=preview)
            print(f"  ✓ {case['id']} ({case.get('intent', '?')})")

    langfuse_flush()


async def run_eval(generate_report: bool) -> None:
    """Run Langfuse LLM-judge evaluation on recent traces."""
    print("\nRunning Langfuse eval...")
    evaluator = Evaluator()
    await evaluator.run(generate_report_file=generate_report)
    print(f"  Traces evaluated: {evaluator.report['total_traces']}")
    print(f"  Report: {evaluator.report.get('generate_report_path', 'N/A')}")


async def main() -> None:
    """Run math teacher agent regression test suite and Langfuse evaluations."""
    parser = argparse.ArgumentParser(description="Math teacher agent regression + eval")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Path to JSON case file",
    )
    parser.add_argument(
        "--mode",
        choices=("agent", "api"),
        default="api",
        help="agent=direct LangGraph; api=HTTP (default)",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API base URL for --mode api")
    parser.add_argument("--cases-only", action="store_true", help="Only seed traces, skip eval")
    parser.add_argument("--eval-only", action="store_true", help="Only run eval, skip cases")
    parser.add_argument("--no-report", action="store_true", help="Skip JSON report generation")
    parser.add_argument(
        "--wait",
        type=int,
        default=5,
        help="Seconds to wait after seeding before eval (Langfuse flush)",
    )
    args = parser.parse_args()

    if not settings.LANGFUSE_TRACING_ENABLED:
        print("Warning: LANGFUSE_TRACING_ENABLED=false — traces will not be recorded.")

    if not args.eval_only:
        cases = load_cases(args.dataset)
        print(f"\nRunning {len(cases)} regression cases ({args.mode} mode)...")
        if args.mode == "agent":
            await run_cases_via_agent(cases)
        else:
            await run_cases_via_api(cases, args.base_url.rstrip("/"))
        if not args.cases_only:
            print(f"\nWaiting {args.wait}s for Langfuse ingest...")
            time.sleep(args.wait)

    if not args.cases_only:
        await run_eval(generate_report=not args.no_report)

    print("\nRegression complete.")


if __name__ == "__main__":
    asyncio.run(main())
