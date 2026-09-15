"""Tests for app/services/shopify_service.py — the real Shopify Admin
REST API client. Every test mocks the actual HTTP boundary via
`httpx.MockTransport` (never the internal service functions), the same
"mock the external dependency, not the internal wiring" convention this
codebase already uses for `call_llm()` — proves the real retry/error/
auth logic actually runs, just against a fake server instead of the
real network.
"""
from __future__ import annotations

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import ShopifyIntegration
from app.services import shopify_service
from app.services.shopify_service import ShopifyAPIError, ShopifyNotConnectedError
from app.services.shopify_service import test_connection as shopify_test_connection


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _connected_integration(db, store_url="test-shop.myshopify.com", token="shpat_fake_token"):
    integration = ShopifyIntegration(store_url=store_url, access_token=token, status="connected")
    db.add(integration)
    db.commit()
    db.refresh(integration)
    return integration


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url=shopify_service._base_url("test-shop"))


# --------------------------------------------------------------------- #
# Not connected
# --------------------------------------------------------------------- #


def test_get_order_raises_not_connected_when_no_integration_row_exists(db_session):
    with pytest.raises(ShopifyNotConnectedError):
        shopify_service.get_order(db_session, 1002)


def test_get_order_raises_not_connected_when_disconnected(db_session):
    db_session.add(ShopifyIntegration(store_url="x.myshopify.com", access_token="", status="disconnected"))
    db_session.commit()
    with pytest.raises(ShopifyNotConnectedError):
        shopify_service.get_order(db_session, 1002)


# --------------------------------------------------------------------- #
# Real request shape (auth header, URL) + success parsing
# --------------------------------------------------------------------- #


def test_get_order_sends_the_real_shopify_auth_header_and_url(db_session):
    _connected_integration(db_session)
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["token_header"] = request.headers.get("X-Shopify-Access-Token")
        return httpx.Response(200, json={"order": {"id": 1002, "name": "#1002", "financial_status": "paid"}})

    order = shopify_service.get_order(db_session, 1002, client=_client(handler))

    assert seen["token_header"] == "shpat_fake_token"
    assert "/admin/api/2024-01/orders/1002.json" in seen["url"]
    assert order == {"id": 1002, "name": "#1002", "financial_status": "paid"}


def test_get_order_404_returns_none_not_an_exception(db_session):
    _connected_integration(db_session)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"errors": "Not Found"})

    assert shopify_service.get_order(db_session, 999999, client=_client(handler)) is None


def test_get_order_401_raises_shopify_api_error_with_status_code(db_session):
    _connected_integration(db_session)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"errors": "Invalid API key or access token"})

    with pytest.raises(ShopifyAPIError) as exc_info:
        shopify_service.get_order(db_session, 1002, client=_client(handler))
    assert exc_info.value.status_code == 401


# --------------------------------------------------------------------- #
# Retries
# --------------------------------------------------------------------- #


def test_a_429_is_retried_and_eventually_succeeds(db_session, monkeypatch):
    monkeypatch.setattr(shopify_service.time, "sleep", lambda _: None)  # don't actually wait in tests
    _connected_integration(db_session)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={"errors": "Throttled"})
        return httpx.Response(200, json={"order": {"id": 1002, "name": "#1002"}})

    order = shopify_service.get_order(db_session, 1002, client=_client(handler))
    assert len(calls) == 3
    assert order["id"] == 1002


def test_a_persistent_5xx_raises_after_exhausting_retries(db_session, monkeypatch):
    monkeypatch.setattr(shopify_service.time, "sleep", lambda _: None)
    _connected_integration(db_session)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503, json={"errors": "Service unavailable"})

    with pytest.raises(ShopifyAPIError):
        shopify_service.get_order(db_session, 1002, client=_client(handler))
    assert len(calls) == shopify_service._MAX_ATTEMPTS


def test_a_non_retryable_400_is_not_retried(db_session, monkeypatch):
    monkeypatch.setattr(shopify_service.time, "sleep", lambda _: None)
    _connected_integration(db_session)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(400, json={"errors": "Bad request"})

    with pytest.raises(ShopifyAPIError):
        shopify_service.get_order(db_session, 1002, client=_client(handler))
    assert len(calls) == 1  # no retry for a plain 400


# --------------------------------------------------------------------- #
# test_connection() — the connect-flow's real credential check
# --------------------------------------------------------------------- #


def test_connection_succeeds_against_a_valid_store(db_session):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("X-Shopify-Access-Token") == "shpat_valid"
        return httpx.Response(200, json={"shop": {"id": 1, "name": "Test Shop", "myshopify_domain": "test-shop.myshopify.com"}})

    shop = shopify_test_connection("test-shop", "shpat_valid", client=_client(handler))
    assert shop["name"] == "Test Shop"


def test_connection_raises_on_bad_credentials():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"errors": "Invalid API key or access token"})

    with pytest.raises(ShopifyAPIError):
        shopify_test_connection("test-shop", "shpat_invalid", client=_client(handler))


# --------------------------------------------------------------------- #
# get_fulfillment_status() — composed from a real order's own shape
# --------------------------------------------------------------------- #


def test_get_fulfillment_status_composes_a_flat_summary(db_session):
    _connected_integration(db_session)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "order": {
                "id": 1002, "name": "#1002", "fulfillment_status": "fulfilled",
                "fulfillments": [{"id": 5, "status": "success", "tracking_company": "UPS", "tracking_number": "1Z999", "tracking_url": "https://ups.com/1Z999", "created_at": "2026-01-01"}],
            }
        })

    result = shopify_service.get_fulfillment_status(db_session, 1002, client=_client(handler))
    assert result["fulfillment_status"] == "fulfilled"
    assert result["fulfillments"][0]["tracking_number"] == "1Z999"


def test_get_fulfillment_status_returns_none_for_a_missing_order(db_session):
    _connected_integration(db_session)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"errors": "Not Found"})

    assert shopify_service.get_fulfillment_status(db_session, 999999, client=_client(handler)) is None


# --------------------------------------------------------------------- #
# search_orders() — real REST filter classification (no fabricated
# `query` param — see search_orders()'s own docstring)
# --------------------------------------------------------------------- #


def test_search_orders_by_email_delegates_to_the_email_filter(db_session):
    _connected_integration(db_session)
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"orders": [{"id": 1002}]})

    results = shopify_service.search_orders(db_session, "alice@example.com", client=_client(handler))
    assert seen["params"]["email"] == "alice@example.com"
    assert results == [{"id": 1002}]


def test_search_orders_by_order_number_uses_the_name_filter(db_session):
    _connected_integration(db_session)
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"orders": [{"id": 1002, "name": "#1002"}]})

    shopify_service.search_orders(db_session, "1002", client=_client(handler))
    assert seen["params"]["name"] == "#1002"
