"""Thin wrapper over the Anthropic SDK. Every agent goes through `call_llm()`
instead of touching the SDK directly, so the model/provider stays swappable
in one place. Implements issue [P0] "Wire a real LLM provider into the
agent stubs".
"""
from __future__ import annotations

from typing import TypeVar

import anthropic
from pydantic import BaseModel

from app.config import settings

T = TypeVar("T", bound=BaseModel)

_client: anthropic.Anthropic | None = None


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


def call_llm(
    system_prompt: str,
    messages: list[dict],
    response_schema: type[T] | None = None,
    max_tokens: int = 4096,
) -> T | str:
    """Call the configured LLM.

    - Without `response_schema`: returns the response's text.
    - With `response_schema` (a Pydantic model): returns a validated
      instance of it via structured outputs. Every agent that needs to act
      on the result (classify, decide, extract) should pass a schema here
      rather than parsing free text itself.
    """
    client = get_client()
    try:
        if response_schema is not None:
            response = client.messages.parse(
                model=settings.llm_model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
                output_format=response_schema,
            )
            return response.parsed_output

        response = client.messages.create(
            model=settings.llm_model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        )
        return next((b.text for b in response.content if b.type == "text"), "")

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
