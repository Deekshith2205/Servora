"""Tests for:
1. app/api/records.py's Shopify record-preview endpoints (backs a
   `shopify_order`/`shopify_customer` evidence reference's inline
   preview — same role as the pre-existing /api/records/orders/{id} etc.
   for Servora's own DB, see test_records_api.py).
2. The full real-tool -> evidence_refs path through a real specialist
   run (app/agents/specialists.py's Shopify branches in
   _describe_evidence()/_describe_evidence_refs()) — Phase 4's actual
   acceptance criterion: evidence_refs must carry
   `{"type": "shopify_order", "ref_id": ..., "label": ...}` automatically,
   with no new evidence system.

Monkeypatches `app.services.shopify_service`'s functions directly (both
records.py and tool_registry.py import that module, not individual
functions, so one patch target covers both call sites) — never a real
network call.
"""
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, SessionLocal
from app.db.models import Customer, ShopifyIntegration
from app.main import app
from app.services.shopify_service import ShopifyAPIError, ShopifyNotConnectedError

_FAKE_ORDER = {
    "id": 1002, "name": "#1002", "email": "alice@example.com",
    "total_price": "59.99", "financial_status": "paid", "fulfillment_status": "fulfilled",
    "created_at": "2026-01-01T00:00:00-00:00",
}
_FAKE_CUSTOMER = {
    "id": 501, "first_name": "Alice", "last_name": "Rao", "email": "alice@example.com",
    "orders_count": 3, "total_spent": "412.50",
}


# --------------------------------------------------------------------- #
# Part 1: /api/records/shopify-orders/{id}, /api/records/shopify-customers/{id}
# --------------------------------------------------------------------- #


def test_get_shopify_order_returns_the_real_looking_fields():
    with patch("app.services.shopify_service.get_order", return_value=_FAKE_ORDER):
        with TestClient(app) as client:
            resp = client.get("/api/records/shopify-orders/1002")

    assert resp.status_code == 200
    body = resp.json()
    assert body["order_number"] == "#1002"
    assert body["financial_status"] == "paid"


def test_get_shopify_order_404_when_shopify_itself_has_no_such_order():
    with patch("app.services.shopify_service.get_order", return_value=None):
        with TestClient(app) as client:
            resp = client.get("/api/records/shopify-orders/999999")
    assert resp.status_code == 404


def test_get_shopify_order_409_when_not_connected():
    with patch("app.services.shopify_service.get_order", side_effect=ShopifyNotConnectedError("not connected")):
        with TestClient(app) as client:
            resp = client.get("/api/records/shopify-orders/1002")
    assert resp.status_code == 409


def test_get_shopify_order_502_on_a_real_shopify_failure():
    with patch("app.services.shopify_service.get_order", side_effect=ShopifyAPIError("Shopify returned 500", status_code=500)):
        with TestClient(app) as client:
            resp = client.get("/api/records/shopify-orders/1002")
    assert resp.status_code == 502


def test_get_shopify_customer_returns_the_real_looking_fields():
    with patch("app.services.shopify_service.get_customer", return_value=_FAKE_CUSTOMER):
        with TestClient(app) as client:
            resp = client.get("/api/records/shopify-customers/501")

    assert resp.status_code == 200
    body = resp.json()
    assert body["first_name"] == "Alice"
    assert body["orders_count"] == 3


# --------------------------------------------------------------------- #
# Part 2: real specialist run -> evidence_refs carries shopify_order
# --------------------------------------------------------------------- #


def _db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _seed_customer(db):
    customer = Customer(name="Alice Rao", email="alice-shopify-evidence@example.com", tier="vip")
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def _tool_use(id_, name, input_):
    block = MagicMock()
    block.type, block.id, block.name, block.input = "tool_use", id_, name, input_
    return block


def _text(text):
    block = MagicMock()
    block.type, block.text = "text", text
    return block


def _response(content, stop_reason):
    resp = MagicMock()
    resp.content, resp.stop_reason = content, stop_reason
    return resp


@patch("app.llm._client", None)
def test_order_specialist_produces_a_real_shopify_order_evidence_ref(monkeypatch):
    """The actual Phase 4 acceptance criterion: a real
    lookup_shopify_order tool call becomes a real
    {"type": "shopify_order", ...} evidence ref, with no separate
    evidence pipeline — same SpecialistResponse.evidence_refs every
    other tool already writes into."""
    from app.agents.specialists import resolve_order

    db = _db_session()
    customer = _seed_customer(db)
    db.add(ShopifyIntegration(store_url="test-shop.myshopify.com", access_token="shpat_x", status="connected"))
    db.commit()

    monkeypatch.setattr("app.services.shopify_service.get_order", lambda db, order_id, client=None: _FAKE_ORDER)

    responses = [
        _response([_tool_use("t1", "lookup_shopify_order", {"order_id": 1002})], "tool_use"),
        _response([_text("Your order #1002 has shipped and was fulfilled.")], "end_turn"),
    ]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses

    with patch("app.llm.get_client", return_value=mock_client):
        result = resolve_order(db, customer.id, "Where is my Shopify order 1002?")

    assert result.evidence_refs == [{"type": "shopify_order", "ref_id": 1002, "label": "Shopify #1002"}]
    assert any("Shopify order #1002" in e for e in result.evidence)
    assert result.confidence == 0.6  # a grounding (non-action) tool was used


@patch("app.llm._client", None)
def test_billing_specialist_gets_an_honest_not_connected_result_when_no_store_is_connected(monkeypatch):
    """No ShopifyIntegration row at all — the tool must return a plain,
    honest "not connected" dict (never raise into the tool-calling loop,
    never fabricate order data) and produce NO evidence_refs, since
    there's no real record to point to."""
    from app.agents.specialists import resolve_billing

    db = _db_session()
    customer = _seed_customer(db)
    # Deliberately no ShopifyIntegration row.

    responses = [
        _response([_tool_use("t1", "lookup_shopify_order", {"order_id": 1002})], "tool_use"),
        _response([_text("I couldn't check that Shopify order — no store is connected yet.")], "end_turn"),
    ]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses

    with patch("app.llm.get_client", return_value=mock_client):
        result = resolve_billing(db, customer.id, "Can you check my Shopify order 1002?")

    assert result.evidence_refs == []
    assert any("not connected" in e.lower() or "connect" in e.lower() for e in result.evidence)


def test_account_specialist_never_receives_the_shopify_tools():
    """Enforces Phase 3's own constraint ("must be callable by Order
    Agent, Billing Agent" — implicitly, nobody else) using the exact
    same permission-boundary test pattern test_tool_permissions.py
    already established."""
    from app.tools.tool_registry import build_filtered_tool_registry

    db = _db_session()
    schemas, handlers = build_filtered_tool_registry(db, "account")
    names = {s["name"] for s in schemas}
    assert "lookup_shopify_order" not in names
    assert "lookup_shopify_customer" not in names
    assert "lookup_shopify_fulfillment" not in names


def test_technical_specialist_never_receives_the_shopify_tools():
    from app.tools.tool_registry import build_filtered_tool_registry

    db = _db_session()
    schemas, handlers = build_filtered_tool_registry(db, "technical")
    names = {s["name"] for s in schemas}
    assert not names & {"lookup_shopify_order", "lookup_shopify_customer", "lookup_shopify_fulfillment"}
