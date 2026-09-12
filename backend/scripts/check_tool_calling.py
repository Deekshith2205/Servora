"""Manual smoke test for Issue #5 — Real LLM tool-calling.

Acceptance criteria: the model is given the get_customer_orders tool and a
customer id. It should request the tool, receive the results, and return a
grounded answer — without hallucinating order details from memory.

Run from backend/ with a real ANTHROPIC_API_KEY in .env:
    .venv/Scripts/python.exe -m scripts.check_tool_calling    # Windows
    python -m scripts.check_tool_calling                      # Unix

DO NOT run this in CI — it makes real network calls.
"""
from __future__ import annotations

import json
import sys

from app.db.database import SessionLocal
from app.llm import LLMError, call_llm
from app.tools.tool_registry import TOOL_SCHEMAS, build_tool_registry

# Demo customer ID seeded by backend/app/db/seed.py
CUSTOMER_ID = 1

SYSTEM_PROMPT = (
    "You are a customer support specialist. Use the available tools to look up "
    "real order data before answering. Never state an order status from memory."
)


def main() -> None:
    db = SessionLocal()
    try:
        tool_schemas, tool_handlers = build_tool_registry(db)
        message = f"Customer {CUSTOMER_ID}: Where is my order? What is the current status?"

        print(f"User message : {message}")
        print(f"Tools exposed: {[s['name'] for s in tool_schemas]}")
        print("-" * 60)

        # Wrap the handler to intercept and print tool calls
        tool_calls_made: list[dict] = []
        original_handlers: dict = dict(tool_handlers)

        def tracing_handler(name: str):
            def _inner(args: dict):
                print(f"\n[TOOL CALLED] {name}({json.dumps(args)})")
                result = original_handlers[name](args)
                print(f"[TOOL RESULT] {result}")
                tool_calls_made.append({"tool": name, "args": args})
                return result
            return _inner

        traced_handlers = {name: tracing_handler(name) for name in original_handlers}

        try:
            answer = call_llm(
                system_prompt=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": message}],
                tools=(tool_schemas, traced_handlers),
            )
        except LLMError as exc:
            print(f"\n[FAILED] LLMError: {exc}", file=sys.stderr)
            sys.exit(1)

        print()
        print("-" * 60)
        print(f"Tool calls made : {len(tool_calls_made)}")
        for tc in tool_calls_made:
            print(f"  {tc['tool']}({tc['args']})")
        print()
        print("Final answer:")
        print(answer)

        if not tool_calls_made:
            print(
                "\n[WARNING] Model answered without calling any tool. "
                "Check the system prompt or model version.",
                file=sys.stderr,
            )
            sys.exit(2)

        print("\n[OK] Smoke test passed.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
