"""Thin wrapper over the configured LLM provider. Every agent goes through
`call_llm()` instead of touching an SDK directly, so the model/provider
stays swappable in one place. Implements issue [P0] "Wire a real LLM
provider into the agent stubs" and issue [P0] "Real tool-calling" (#5).

Provider note: originally Anthropic-only despite `settings.llm_provider`
existing as a setting (it was never actually branched on). A Gemini path
was added so the app can run on Google AI Studio's free tier as a
hackathon-prototype fallback when no Anthropic credit is available — set
`LLM_PROVIDER=gemini` + `GOOGLE_API_KEY` in `.env` to switch. Default
stays `"anthropic"`, so nothing changes for an existing `.env` unless
someone explicitly opts in. Both paths implement the exact same
`call_llm()` contract (structured output via `response_schema`, the same
tool-calling loop shape, the same `LLMError` on any unrecoverable
failure) so no calling agent needs to know or care which provider is
active.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, TypeVar

import anthropic
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from pydantic import BaseModel

from app.config import settings

T = TypeVar("T", bound=BaseModel)

_client: anthropic.Anthropic | None = None
_gemini_client: genai.Client | None = None
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
    """Lazily construct a single shared Anthropic client.

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


def get_gemini_client() -> genai.Client:
    """Lazily construct a single shared Gemini client — mirrors get_client()."""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = (
            genai.Client(api_key=settings.google_api_key)
            if settings.google_api_key
            else genai.Client()
        )
    return _gemini_client


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
    """Call the configured provider (`settings.llm_provider`), optionally
    with tool-calling.

    Existing callers are fully backward-compatible — ``tools`` and
    ``tool_call_log`` both default to ``None`` and the plain-text /
    structured-output paths are unchanged. This function is just a
    dispatcher; see ``_call_anthropic`` / ``_call_gemini`` for the actual
    provider-specific implementations, which both honor the same contract
    described below.

    When ``tools`` is supplied it must be a 2-tuple:
      - ``tool_schemas``: list of ToolParam-shaped dicts (name, description,
        input_schema — standard JSON Schema) — use ``build_tool_registry(db)``
        from ``app.tools.tool_registry`` to obtain these.
      - ``tool_handlers``: dict mapping tool name → callable that accepts the
        LLM-supplied ``input`` dict and returns a Python value. The result is
        serialized to JSON before being fed back to the model as a tool
        result.

    Pass a mutable list as ``tool_call_log`` to have every tool name the
    model requests appended to it, in call order (including unknown/failed
    calls — the log records what was *attempted*, for the reasoning trace).
    Useful for populating something like a specialist's ``used_tools`` field
    without changing ``call_llm``'s return type.

    Tool-calling loop (repeated up to ``_MAX_TOOL_ITERATIONS`` times):
      1. Send messages + tool schemas to the model.
      2. If it requests one or more tool calls, execute each, append the
         model's turn and a tool-result turn, then call again.
      3. Repeat until no more tool calls are requested, or the iteration
         limit is hit (raises ``LLMError``).

    Unknown tool names and exceptions raised by a tool handler are caught and
    returned to the model as an error result rather than crashing the
    process.

    ``response_schema`` is not supported together with ``tools`` — structured
    output requires a dedicated parse call that does not support
    tool-calling on either provider. Pass ``None`` for ``response_schema``
    when using tools.
    """
    if settings.llm_provider == "gemini":
        return _call_gemini(system_prompt, messages, response_schema, max_tokens, tools, tool_call_log)
    return _call_anthropic(system_prompt, messages, response_schema, max_tokens, tools, tool_call_log)


def _call_anthropic(
    system_prompt: str,
    messages: list[dict],
    response_schema: type[T] | None,
    max_tokens: int,
    tools: tuple[list[dict], dict[str, Callable[[dict], Any]]] | None,
    tool_call_log: list[str] | None,
) -> T | str:
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

    except LLMError:
        raise  # already well-formed (e.g. the tool-loop iteration-limit error) — don't rewrap
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
    except Exception as e:  # noqa: BLE001 — see docstring note below
        # Found while verifying issue #17 live: with no credentials resolvable
        # at all (as opposed to a live request being rejected), the Anthropic
        # SDK raises a bare TypeError, not an anthropic.* exception — none of
        # the clauses above catch it. Every "best-effort" caller in this
        # codebase (memory extraction, escalation packets, KB drafts) does
        # `except LLMError: <degrade gracefully>`; without this clause, that
        # degrade-gracefully path silently never triggered whenever no API
        # key was configured at all, and the whole request 500'd instead —
        # exactly the "no API key" case every demo runs into by default.
        raise LLMError(f"Unexpected error calling the LLM: {type(e).__name__}: {e}") from e


def _to_gemini_contents(messages: list[dict]) -> list[genai_types.Content]:
    """Translate the existing ``{"role": "user"|"assistant", "content": str}``
    shape (unchanged across both providers) into Gemini's ``Content``
    objects. Gemini calls the assistant's own turns "model", not
    "assistant" — every other role name passes through unchanged."""
    role_map = {"assistant": "model"}
    return [
        genai_types.Content(
            role=role_map.get(m["role"], m["role"]),
            parts=[genai_types.Part.from_text(text=m["content"])],
        )
        for m in messages
    ]


def _call_gemini(
    system_prompt: str,
    messages: list[dict],
    response_schema: type[T] | None,
    max_tokens: int,
    tools: tuple[list[dict], dict[str, Callable[[dict], Any]]] | None,
    tool_call_log: list[str] | None,
) -> T | str:
    """Gemini equivalent of ``_call_anthropic`` — same contract, same tool
    loop shape, same ``LLMError`` wrapping, different SDK underneath. See
    that function's inline comments for the shared design rationale
    (validate-before-execute, never leak tool tracebacks to the model,
    iteration cap, etc.) — not repeated here.
    """
    from app.tools.tool_registry import serialize_tool_result

    try:
        # Unlike Anthropic's SDK (which defers an auth failure to call
        # time), google-genai's Client() raises ValueError immediately at
        # construction if no API key/project is configured — so client
        # acquisition has to be INSIDE the try here, or a missing key
        # would propagate as a bare, uncaught ValueError instead of a
        # clean LLMError (exactly the class of bug fixed for the
        # Anthropic path in issue #17).
        client = get_gemini_client()

        # Found live verifying this against a real key: several current
        # Gemini models (e.g. gemini-3.6-flash) "think" before answering by
        # default, spending part of max_output_tokens on invisible
        # reasoning tokens the caller never sees — with the token budgets
        # already in use throughout this codebase (as low as 300 for the
        # classifier), that silently exhausted the whole budget before any
        # visible output, returning None with finish_reason=MAX_TOKENS. A
        # flat thinking_budget=0 is rejected as an invalid argument by this
        # model (thinking can't be fully disabled on every model, despite
        # what the SDK's own docstring implies) — thinking_level="MINIMAL"
        # is the setting that actually works across the models tried here.
        _thinking_config = genai_types.ThinkingConfig(thinking_level="MINIMAL")

        if response_schema is not None:
            response = client.models.generate_content(
                model=settings.llm_model,
                contents=_to_gemini_contents(messages),
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=max_tokens,
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    thinking_config=_thinking_config,
                ),
            )
            return response.parsed

        tool_schemas, tool_handlers = tools if tools is not None else (None, {})
        contents = _to_gemini_contents(messages)

        config_kwargs: dict = dict(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
            thinking_config=_thinking_config,
        )
        if tool_schemas:
            config_kwargs["tools"] = [
                genai_types.Tool(
                    function_declarations=[
                        genai_types.FunctionDeclaration(
                            name=s["name"],
                            description=s.get("description", ""),
                            # Raw JSON Schema (same input_schema dicts every
                            # tool registry already builds for Anthropic) —
                            # parameters_json_schema takes it as-is, unlike
                            # `parameters`, which expects Gemini's own Schema
                            # dataclass shape.
                            parameters_json_schema=s.get("input_schema"),
                        )
                        for s in tool_schemas
                    ]
                )
            ]

        for iteration in range(_MAX_TOOL_ITERATIONS + 1):
            if iteration == _MAX_TOOL_ITERATIONS:
                raise LLMError(
                    f"Tool-calling loop exceeded {_MAX_TOOL_ITERATIONS} iterations "
                    "without reaching a final answer. Check the tool schemas and "
                    "system prompt for convergence issues."
                )

            response = client.models.generate_content(
                model=settings.llm_model,
                contents=contents,
                config=genai_types.GenerateContentConfig(**config_kwargs),
            )

            function_calls = response.function_calls or []
            if not function_calls:
                return response.text or ""

            # The model's own turn (including its function_call parts) must
            # be replayed back so it sees what it asked for — analogous to
            # appending {"role": "assistant", "content": response.content}
            # in the Anthropic path.
            contents.append(response.candidates[0].content)

            function_response_parts = []
            for fc in function_calls:
                tool_name = fc.name
                tool_input = fc.args or {}

                if tool_call_log is not None:
                    tool_call_log.append(tool_name)

                if tool_name not in tool_handlers:
                    function_response_parts.append(
                        genai_types.Part.from_function_response(
                            name=tool_name, response={"error": f"Unknown tool: {tool_name!r}"}
                        )
                    )
                    continue

                schema = next((s for s in (tool_schemas or []) if s["name"] == tool_name), None)
                validation_error = _validate_tool_args(tool_name, tool_input, schema)
                if validation_error:
                    function_response_parts.append(
                        genai_types.Part.from_function_response(
                            name=tool_name, response={"error": validation_error}
                        )
                    )
                    continue

                try:
                    raw_result = tool_handlers[tool_name](tool_input)
                    result_json = serialize_tool_result(raw_result)
                except Exception as exc:  # noqa: BLE001
                    _log.warning(
                        "Tool %r execution failed: %s: %s", tool_name, type(exc).__name__, exc
                    )
                    function_response_parts.append(
                        genai_types.Part.from_function_response(
                            name=tool_name,
                            response={"error": "Tool execution failed. Please try again or use another tool."},
                        )
                    )
                    continue

                function_response_parts.append(
                    genai_types.Part.from_function_response(name=tool_name, response={"result": result_json})
                )

            contents.append(genai_types.Content(role="user", parts=function_response_parts))

        raise LLMError("Unexpected exit from tool-calling loop.")  # pragma: no cover

    except LLMError:
        raise
    except ValueError as e:
        # google-genai's Client() raises this at construction when no
        # API key/project is configured at all (see the comment above
        # get_gemini_client()'s call site) — the Gemini equivalent of the
        # bare TypeError issue #17 found on the Anthropic side.
        raise LLMError(
            "Google API key is missing or invalid — copy backend/.env.example "
            "to .env, set GOOGLE_API_KEY to your own key, and LLM_PROVIDER=gemini."
        ) from e
    except genai_errors.ClientError as e:
        if e.code in (401, 403):
            raise LLMError(
                "Google API key is missing or invalid — copy backend/.env.example "
                "to .env, set GOOGLE_API_KEY to your own key, and LLM_PROVIDER=gemini."
            ) from e
        if e.code == 429:
            raise LLMError("Rate limited by the Gemini API — retry shortly.") from e
        raise LLMError(f"Gemini API error ({e.code}): {e.message}") from e
    except genai_errors.ServerError as e:
        raise LLMError(f"Gemini API error ({e.code}): {e.message}") from e
    except Exception as e:  # noqa: BLE001 — same rationale as _call_anthropic's catch-all
        raise LLMError(f"Unexpected error calling the LLM: {type(e).__name__}: {e}") from e
