"""[RAG] Phase 4: Embeddings & Vector Storage — #242 embedding service
abstraction, #244 embedding generation.

A real, already-available choice, not a new integration: `google-genai`
is already a pinned, configured dependency (`GOOGLE_API_KEY`,
`settings.llm_provider`), and Gemini offers a real embeddings API.
Anthropic's Claude models do not offer one at all — see #225's own epic
description. This module therefore has exactly ONE real backing
implementation (Gemini), documented honestly as such rather than built
as a two-provider abstraction with a fake second option. It is a
separate client/call from `app/llm.py::call_llm()` (embeddings are not
a chat completion), but reuses the exact same `settings.google_api_key`
credential and the same "lazily construct one shared client" pattern as
`get_gemini_client()`.
"""
from __future__ import annotations

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from app.config import settings

# gemini-embedding-001 — confirmed live against the real configured key
# (3072-dim vectors). A fixed model name, not settings.llm_model: that
# setting controls the CHAT model (Anthropic or Gemini) and has no
# embedding equivalent on the Anthropic side at all, so embeddings are
# deliberately never swapped by LLM_PROVIDER — this app always embeds
# with Gemini regardless of which provider serves chat.
EMBEDDING_MODEL = "gemini-embedding-001"

_client: genai.Client | None = None


class EmbeddingError(RuntimeError):
    """Raised for any unrecoverable failure generating an embedding —
    mirrors `app.llm.LLMError`'s role for the chat path."""


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = (
            genai.Client(api_key=settings.google_api_key)
            if settings.google_api_key
            else genai.Client()
        )
    return _client


def embed_texts(texts: list[str], *, task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """Embed a batch of texts. ``task_type`` is Gemini's own hint for
    which embedding variant to compute — "RETRIEVAL_DOCUMENT" when
    indexing a chunk (the default, since indexing is this function's
    most common caller), "RETRIEVAL_QUERY" when embedding a search
    query (`knowledge_retrieval.search_knowledge()` passes this
    explicitly) — Gemini's own documented reason two embeddings of the
    same model can be meaningfully compared for similarity at all.

    Returns one embedding vector per input text, in the same order.
    Raises ``EmbeddingError`` on any failure — empty input, a missing/
    invalid API key, a rate limit, or any other API error — never lets a
    raw SDK exception (or a bare `ValueError`/`TypeError` the way
    `app.llm` documented for the chat path) propagate to a caller that
    doesn't know Gemini's own SDK.
    """
    if not texts:
        return []
    try:
        client = _get_client()
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texts,
            config=genai_types.EmbedContentConfig(task_type=task_type),
        )
        return [list(e.values) for e in response.embeddings]
    except EmbeddingError:
        raise
    except ValueError as e:
        # Mirrors app.llm._call_gemini's own finding: Client() raises a
        # bare ValueError at construction when no API key is configured
        # at all.
        raise EmbeddingError(
            "Google API key is missing or invalid — copy backend/.env.example "
            "to .env and set GOOGLE_API_KEY to your own key."
        ) from e
    except genai_errors.ClientError as e:
        if e.code in (401, 403):
            raise EmbeddingError(
                "Google API key is missing or invalid — copy backend/.env.example "
                "to .env and set GOOGLE_API_KEY to your own key."
            ) from e
        if e.code == 429:
            raise EmbeddingError("Rate limited by the Gemini embeddings API — retry shortly.") from e
        raise EmbeddingError(f"Gemini embeddings API error ({e.code}): {e.message}") from e
    except genai_errors.ServerError as e:
        raise EmbeddingError(f"Gemini embeddings API error ({e.code}): {e.message}") from e
    except Exception as e:  # noqa: BLE001 — same catch-all rationale as app.llm
        raise EmbeddingError(f"Unexpected error generating embeddings: {type(e).__name__}: {e}") from e


def embed_text(text: str, *, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    """Single-text convenience wrapper over `embed_texts()`."""
    return embed_texts([text], task_type=task_type)[0]
