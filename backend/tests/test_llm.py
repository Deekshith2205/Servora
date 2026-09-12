"""Tests that don't require a real API key — network-hitting verification
is scripts/check_llm.py (run manually with your own key), per this issue's
acceptance criteria.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.llm import LLMError, call_llm, get_client


def test_llm_error_is_a_runtime_error():
    assert issubclass(LLMError, RuntimeError)


def test_get_client_constructs_without_network_call():
    # Client construction must not itself make a request — should succeed
    # even with no key configured (the SDK only fails at call time).
    client = get_client()
    assert client is not None
    # Calling again returns the same cached instance.
    assert get_client() is client


@patch("app.llm._client", None)
def test_unexpected_exception_is_wrapped_as_llm_error():
    """Found while verifying issue #17 live: with no credentials
    resolvable at all, the Anthropic SDK raises a bare TypeError — not an
    anthropic.* exception — which none of the specific except clauses
    caught. Every best-effort caller in this codebase does
    `except LLMError: <degrade gracefully>`, so an uncaught TypeError
    silently broke that path whenever no API key was configured."""
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = TypeError("Could not resolve authentication method.")

    with patch("app.llm.get_client", return_value=mock_client):
        with pytest.raises(LLMError):
            call_llm(system_prompt="test", messages=[{"role": "user", "content": "hi"}])


@patch("app.llm._client", None)
def test_llm_error_raised_inside_call_llm_is_not_double_wrapped():
    """The tool-loop iteration-limit error (and similar) already raises a
    well-formed LLMError from inside the try block — the catch-all must
    not wrap it in a second LLMError with a mangled message."""
    mock_client = MagicMock()
    # stop_reason "tool_use" forever with no matching handler exhausts the
    # iteration limit, which itself raises LLMError from inside call_llm.
    tool_block = MagicMock()
    tool_block.type, tool_block.id, tool_block.name, tool_block.input = "tool_use", "t1", "unknown_tool", {}
    response = MagicMock()
    response.content, response.stop_reason = [tool_block], "tool_use"
    mock_client.messages.create.return_value = response

    with patch("app.llm.get_client", return_value=mock_client):
        with pytest.raises(LLMError, match="iterations"):
            call_llm(
                system_prompt="test",
                messages=[{"role": "user", "content": "hi"}],
                tools=([{"name": "unknown_tool", "input_schema": {}}], {}),
            )
