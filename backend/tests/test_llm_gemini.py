"""Tests for the Gemini provider path (app/llm.py::_call_gemini), added so
this project can run on Google AI Studio's free tier as a hackathon-
prototype fallback when no Anthropic credit is available — see
LLM_PROVIDER in app/config.py. Same network-free mocking philosophy as
test_llm.py: only google.genai's client is mocked, never a real request.
"""
from unittest.mock import MagicMock, patch

import pytest
from google.genai import errors as genai_errors
from pydantic import BaseModel

from app.llm import LLMError, call_llm, get_gemini_client


@patch("app.config.settings.google_api_key", "dummy-key-for-construction-only")
@patch("app.llm._gemini_client", None)
def test_get_gemini_client_constructs_without_network_call():
    # Unlike Anthropic's SDK (which defers an auth failure to call time),
    # google-genai's Client() raises immediately at construction if no
    # key/project is configured at all — so this test, unlike its
    # Anthropic equivalent, needs a key present to reach "constructs
    # successfully" at all. The missing-key case is covered by
    # test_gemini_missing_key_raises_llm_error_not_a_bare_valueerror below.
    client = get_gemini_client()
    assert client is not None
    assert get_gemini_client() is client


@patch("app.config.settings.llm_provider", "gemini")
@patch("app.config.settings.google_api_key", "")
@patch("app.llm._gemini_client", None)
def test_gemini_missing_key_raises_llm_error_not_a_bare_valueerror():
    """google-genai's Client() raises a bare ValueError at construction
    when no key is configured — the Gemini equivalent of the bare
    TypeError issue #17 found on the Anthropic side. Must become a clean
    LLMError, not propagate as-is."""
    with pytest.raises(LLMError, match="Google API key"):
        call_llm(system_prompt="test", messages=[{"role": "user", "content": "hi"}])


class _Reply(BaseModel):
    text: str


@patch("app.config.settings.llm_provider", "gemini")
@patch("app.llm._gemini_client", None)
def test_call_llm_dispatches_to_gemini_and_returns_parsed_output():
    mock_response = MagicMock()
    mock_response.parsed = _Reply(text="hello from gemini")
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.llm.get_gemini_client", return_value=mock_client):
        result = call_llm(
            system_prompt="test",
            messages=[{"role": "user", "content": "hi"}],
            response_schema=_Reply,
        )

    assert result.text == "hello from gemini"
    # Structured-output call must request JSON + the schema, not tool-calling.
    _, kwargs = mock_client.models.generate_content.call_args
    assert kwargs["config"].response_mime_type == "application/json"
    assert kwargs["config"].response_schema is _Reply


def _function_call(name: str, args: dict):
    fc = MagicMock()
    fc.name, fc.args = name, args
    return fc


@patch("app.config.settings.llm_provider", "gemini")
@patch("app.llm._gemini_client", None)
def test_gemini_tool_loop_executes_tool_then_returns_final_text():
    tool_response = MagicMock()
    tool_response.function_calls = [_function_call("get_thing", {"id": 1})]
    tool_response.candidates = [MagicMock(content=MagicMock())]

    final_response = MagicMock()
    final_response.function_calls = []
    final_response.text = "final reply"

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [tool_response, final_response]

    used_tools: list[str] = []
    handler = MagicMock(return_value={"ok": True})

    with patch("app.llm.get_gemini_client", return_value=mock_client):
        result = call_llm(
            system_prompt="test",
            messages=[{"role": "user", "content": "hi"}],
            tools=([{"name": "get_thing", "description": "d", "input_schema": {"type": "object", "properties": {}}}],
                   {"get_thing": handler}),
            tool_call_log=used_tools,
        )

    assert result == "final reply"
    assert used_tools == ["get_thing"]
    handler.assert_called_once_with({"id": 1})


@patch("app.config.settings.llm_provider", "gemini")
@patch("app.llm._gemini_client", None)
def test_gemini_unknown_tool_reported_gracefully_not_raised():
    tool_response = MagicMock()
    tool_response.function_calls = [_function_call("mystery_tool", {})]
    tool_response.candidates = [MagicMock(content=MagicMock())]

    final_response = MagicMock()
    final_response.function_calls = []
    final_response.text = "handled it anyway"

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [tool_response, final_response]

    with patch("app.llm.get_gemini_client", return_value=mock_client):
        result = call_llm(
            system_prompt="test",
            messages=[{"role": "user", "content": "hi"}],
            tools=([{"name": "known_tool", "description": "d", "input_schema": {}}], {}),
        )

    assert result == "handled it anyway"


@patch("app.config.settings.llm_provider", "gemini")
@patch("app.llm._gemini_client", None)
def test_gemini_iteration_limit_raises_llm_error():
    looping_response = MagicMock()
    looping_response.function_calls = [_function_call("get_thing", {})]
    looping_response.candidates = [MagicMock(content=MagicMock())]

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = looping_response

    with patch("app.llm.get_gemini_client", return_value=mock_client):
        with pytest.raises(LLMError, match="iterations"):
            call_llm(
                system_prompt="test",
                messages=[{"role": "user", "content": "hi"}],
                tools=([{"name": "get_thing", "description": "d", "input_schema": {}}],
                       {"get_thing": lambda args: "result"}),
            )


@patch("app.config.settings.llm_provider", "gemini")
@patch("app.llm._gemini_client", None)
def test_gemini_auth_error_wrapped_as_llm_error():
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = genai_errors.ClientError(
        code=401, response_json={"error": {"message": "invalid API key", "status": "UNAUTHENTICATED"}}
    )

    with patch("app.llm.get_gemini_client", return_value=mock_client):
        with pytest.raises(LLMError, match="Google API key"):
            call_llm(system_prompt="test", messages=[{"role": "user", "content": "hi"}])


@patch("app.config.settings.llm_provider", "gemini")
@patch("app.llm._gemini_client", None)
def test_gemini_rate_limit_wrapped_as_llm_error():
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = genai_errors.ClientError(
        code=429, response_json={"error": {"message": "quota exceeded", "status": "RESOURCE_EXHAUSTED"}}
    )

    with patch("app.llm.get_gemini_client", return_value=mock_client):
        with pytest.raises(LLMError, match="Rate limited"):
            call_llm(system_prompt="test", messages=[{"role": "user", "content": "hi"}])


@patch("app.config.settings.llm_provider", "gemini")
@patch("app.llm._gemini_client", None)
def test_gemini_unexpected_exception_wrapped_as_llm_error():
    """Same defensive catch-all as the Anthropic path (issue #17) — a
    completely unanticipated exception from the SDK must still become a
    clean LLMError, not crash the caller."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = TypeError("something the SDK never documented")

    with patch("app.llm.get_gemini_client", return_value=mock_client):
        with pytest.raises(LLMError):
            call_llm(system_prompt="test", messages=[{"role": "user", "content": "hi"}])


def test_call_llm_still_dispatches_to_anthropic_by_default():
    """Regression guard: adding the Gemini path must not change the
    default provider for every existing caller/test."""
    from app.config import settings
    assert settings.llm_provider == "anthropic"
