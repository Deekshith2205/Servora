"""Thin wrapper over the Anthropic SDK. Every agent goes through `call_llm()`
instead of touching the SDK directly, so the model/provider stays swappable
in one place. Implements issue [P0] "Wire a real LLM provider into the
agent stubs" and issue [P0] "Real tool-calling" (#5).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, TypeVar

import anthropic
from pydantic import BaseModel

from app.config import settings

T = TypeVar("T", bound=BaseModel)

_client: anthropic.Anthropic | None = None
_log = logging.getLogger(__name__)

# Maximum number of tool-call ↔ tool-result round-trips before giving up.
# Prevents runaway loops if the model keeps requesting tools without converging.
_MAX_TOOL_ITERATIONS = 10

# Map of JSON schema primitive type names to the Python types they represent.
# Used to validate LLM-supplied tool arguments before they reach the database.
_JSON_TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "integer": int,
    "number": (int, float),
    "string": str,
    "boolean": bool,
    "array": list,
    "object": dict,
}


class LLMError(RuntimeError):
    """Raised for any unrecoverable failure calling the LLM.

    Agents should let this propagate — the orchestrator/API layer decides
    how to surface it (e.g. as a 502, or as an escalation) rather than
    every agent handling it individually.
    """


def get_client() -> anthropic.Anthropic:
    """Lazily construct a single shared client.

    Uses the explicit key from settings/.env when one is configured (keeps
    deploys portable); otherwise falls back to the SDK's own credential
    resolution (ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN / `ant auth login`
    profile), which is useful for local dev.
    """
    global _client
    if _client is None:
        _client = (
            anthropic.Anthropic(api_key=settings.anthropic_api_key)
            if settings.anthropic_api_key
            else anthropic.Anthropic()
        )
    return _client


def _validate_tool_args(
    tool_name: str,
    args: dict,
    schema: dict | None,
) -> str | None:
    """Validate LLM-supplied tool arguments against the tool's ``input_schema``.

    Returns ``None`` when all required arguments are present and have the
    correct JSON types. Returns a safe human-readable error string (suitable
    for a ``tool_result`` error message) when validation fails.

    Validation is intentionally lightweight — it only checks:
      1. Required fields are present.
      2. Present fields have the type declared in ``input_schema.properties``.

    The goal is to block obviously malformed LLM output from reaching the
    database, not to implement full JSON Schema validation.
    """
    if schema is None:
        return None  # No schema available — let the handler fail naturally

    input_schema = schema.get("input_schema", {})
    properties: dict = input_schema.get("properties", {})
    required: list[str] = input_schema.get("required", [])

    # 1. Check required fields are present
    missing = [field for field in required if field not in args]
    if missing:
        return (
            f"Tool {tool_name!r} called with missing required argument(s): "
            + ", ".join(repr(f) for f in missing)
            + ". Please supply all required arguments and try again."
        )

    # 2. Check type of each supplied field that has a declared type
    for field, value in args.items():
        prop_def = properties.get(field)
        if prop_def is None:
            continue  # Extra/unknown fields pass through silently
        declared_type = prop_def.get("type")
        if declared_type is None:
            continue
        expected_py_type = _JSON_TYPE_MAP.get(declared_type)
        if expected_py_type is None:
            continue  # Unknown JSON type — skip
        # Note: JSON integers are also valid Python bools; exclude bools when
        # the schema expects a numeric type.
        if declared_type in ("integer", "number") and isinstance(value, bool):
            return (
                f"Tool {tool_name!r} argument {field!r} must be {declared_type}, "
                f"got boolean. Please provide a numeric value."
            )
        if not isinstance(value, expected_py_type):
            return (
                f"Tool {tool_name!r} argument {field!r} must be {declared_type}, "
                f"got {type(value).__name__!r}. Please correct the argument type."
            )

    return None  # All checks passed


def call_llm(
    system_prompt: str,
    messages: list[dict],
    response_schema: type[T] | None = None,
    max_tokens: int = 4096,
    tools: tuple[list[dict], dict[str, Callable[[dict], Any]]] | None = None,
    tool_call_log: list[str] | None = None,
) -> T | str:
    """Call the configured LLM, optionally with Anthropic tool-calling.

    Existing callers are fully backward-compatible — ``tools`` and
    ``tool_call_log`` both default to ``None`` and the plain-text /
    structured-output paths are unchanged.

    When ``tools`` is supplied it must be a 2-tuple:
      - ``tool_schemas``: list of Anthropic ToolParam dicts (name, description,
        input_schema) — use ``build_tool_registry(db)`` from
        ``app.tools.tool_registry`` to obtain these.
      - ``tool_handlers``: dict mapping tool name → callable that accepts the
        LLM-supplied ``input`` dict and returns a Python value. The result is
        serialized to JSON before being fed back to the model as a
        ``tool_result`` message.

    Pass a mutable list as ``tool_call_log`` to have every tool name the
    model requests appended to it, in call order (including unknown/failed
    calls — the log records what was *attempted*, for the reasoning trace).
    Useful for populating something like a specialist's ``used_tools`` field
    without changing ``call_llm``'s return type.

    Tool-calling loop (repeated up to ``_MAX_TOOL_ITERATIONS`` times):
      1. Send messages + tool schemas to Anthropic.
      2. If ``stop_reason == "tool_use"``, execute each requested tool,
         append the assistant response and a ``tool_result`` user message,
         then call Anthropic again.
      3. Repeat until ``stop_reason != "tool_use"`` or the iteration limit
         is hit (raises ``LLMError``).

    Unknown tool names and exceptions raised by a tool handler are caught and
    returned to the model as tool_result error content rather than crashing the
    process.

    ``response_schema`` is not supported together with ``tools`` — structured
    output requires ``messages.parse`` which does not support tool-calling.
    Pass ``None`` for ``response_schema`` when using tools.
    """
    from app.tools.tool_registry import serialize_tool_result  # local import keeps llm.py import-clean

    client = get_client()
    try:
        # ------------------------------------------------------------------ #
        # Fast path: structured output (no tool-calling support needed here)  #
        # ------------------------------------------------------------------ #
        if response_schema is not None:
            response = client.messages.parse(
                model=settings.llm_model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
                output_format=response_schema,
            )
            return response.parsed_output

        # ------------------------------------------------------------------ #
        # Plain text path — may include tool-calling loop                     #
        # ------------------------------------------------------------------ #
        tool_schemas, tool_handlers = tools if tools is not None else (None, {})

        # Build a mutable copy so we can append tool results without mutating
        # the caller's list.
        conversation: list[dict] = list(messages)

        create_kwargs: dict = dict(
            model=settings.llm_model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=conversation,
        )
        if tool_schemas:
            create_kwargs["tools"] = tool_schemas

        for iteration in range(_MAX_TOOL_ITERATIONS + 1):
            if iteration == _MAX_TOOL_ITERATIONS:
                raise LLMError(
                    f"Tool-calling loop exceeded {_MAX_TOOL_ITERATIONS} iterations "
                    "without reaching a final answer. Check the tool schemas and "
                    "system prompt for convergence issues."
                )

            response = client.messages.create(**create_kwargs)

            # No tool calls — return the text response
            if response.stop_reason != "tool_use":
                return next((b.text for b in response.content if b.type == "text"), "")

            # ---- Execute all requested tools in this response ------------- #
            tool_result_content: list[dict] = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_name: str = block.name
                tool_input: dict = block.input  # type: ignore[assignment]
                tool_use_id: str = block.id

                if tool_call_log is not None:
                    tool_call_log.append(tool_name)

                if tool_name not in tool_handlers:
                    # Unknown tool — report gracefully so the model can recover
                    tool_result_content.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "is_error": True,
                        "content": f"Unknown tool: {tool_name!r}",
                    })
                    continue

                # --- Validate arguments against the tool's input_schema ---- #
                schema = next(
                    (s for s in (tool_schemas or []) if s["name"] == tool_name), None
                )
                validation_error = _validate_tool_args(tool_name, tool_input, schema)
                if validation_error:
                    tool_result_content.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "is_error": True,
                        "content": validation_error,
                    })
                    continue

                try:
                    raw_result = tool_handlers[tool_name](tool_input)
                    result_json = serialize_tool_result(raw_result)
                except Exception as exc:  # noqa: BLE001
                    # Log locally for debugging, but never expose DB details
                    # or Python tracebacks to the model.
                    _log.warning(
                        "Tool %r execution failed: %s: %s",
                        tool_name, type(exc).__name__, exc,
                    )
                    tool_result_content.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "is_error": True,
                        "content": "Tool execution failed. Please try again or use another tool.",
                    })
                    continue

                tool_result_content.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": result_json,
                })

            # Append the assistant message (with tool_use blocks) and the
            # aggregated tool_result user message, then loop.
            conversation.append({"role": "assistant", "content": response.content})
            conversation.append({"role": "user", "content": tool_result_content})
            create_kwargs["messages"] = conversation

        # Unreachable — the for-loop raises LLMError before this
        raise LLMError("Unexpected exit from tool-calling loop.")  # pragma: no cover

    except anthropic.AuthenticationError as e:
        raise LLMError(
            "Anthropic API key is missing or invalid — copy backend/.env.example "
            "to .env and set ANTHROPIC_API_KEY to your own key."
        ) from e
    except anthropic.RateLimitError as e:
        raise LLMError("Rate limited by the Anthropic API — retry shortly.") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Anthropic API error ({e.status_code}): {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise LLMError("Could not reach the Anthropic API — check your network connection.") from e
