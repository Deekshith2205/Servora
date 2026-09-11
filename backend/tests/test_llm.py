"""Tests that don't require a real API key — network-hitting verification
is scripts/check_llm.py (run manually with your own key), per this issue's
acceptance criteria.
"""
from app.llm import LLMError, get_client


def test_llm_error_is_a_runtime_error():
    assert issubclass(LLMError, RuntimeError)


def test_get_client_constructs_without_network_call():
    # Client construction must not itself make a request — should succeed
    # even with no key configured (the SDK only fails at call time).
    client = get_client()
    assert client is not None
    # Calling again returns the same cached instance.
    assert get_client() is client
