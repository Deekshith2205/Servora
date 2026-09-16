"""[RBAC] issue #223 — full permission testing matrix.

A single, explicit table of (endpoint, role) -> allowed/forbidden,
parametrized across all 4 real roles plus the anonymous (no identity
headers) actor. Complements, rather than duplicates, the individual
positive/negative tests already embedded in each feature's own test
file (e.g. `test_channels_api.py::test_patch_without_permission_is_a_real_403`)
— this file's job is to prove the ENTIRE matrix agrees with
`app/auth/permissions.py::ROLE_PERMISSIONS`, not just one spot-check
per endpoint.

Scoped to GET endpoints only (idempotent, safe to run in any order on
the shared test DB) — the write-path (POST/PATCH) 403 checks already
live next to each feature's own tests (test_channels_api.py,
test_integrations_api.py, test_kb_api.py, test_users_api.py,
test_settings_api.py, test_tickets_api.py).
"""
import pytest
from fastapi.testclient import TestClient

from app.agents.classifier import ClassificationResult
from app.agents.critic import CriticReview
from app.agents.planner import PlanDecision
from app.agents.specialists import SpecialistResponse
from app.agents.verification import VerificationResult
from app.db.database import SessionLocal
from app.db.models import Customer, Order, Ticket
from app.main import app
from tests.rbac_headers import customer_headers, staff_headers

client = TestClient(app)

_MOCK_CRITIC_REVIEW = CriticReview(agrees=True, confidence=0.8, alternative_hypothesis=None, reasoning="mocked for test")

ALL_ROLES = ["anonymous", "customer", "support_agent", "manager", "administrator"]


def _headers_for(role: str, db, customer_id: int) -> dict:
    if role == "anonymous":
        return {}
    if role == "customer":
        return customer_headers(customer_id)
    return staff_headers(db, role)


@pytest.fixture(scope="module")
def matrix_customer():
    db = SessionLocal()
    customer = Customer(name="Matrix Test Customer", email="rbac-matrix@example.com", tier="standard")
    db.add(customer)
    db.commit()
    db.refresh(customer)
    order = Order(customer_id=customer.id, product="Matrix Widget", amount=10.0, status="shipped", payment_status="paid")
    db.add(order)
    ticket = Ticket(customer_id=customer.id, category="order", subject="Matrix ticket", message="m", status="open")
    db.add(ticket)
    db.commit()
    db.refresh(order)
    db.refresh(ticket)
    return {"customer_id": customer.id, "order_id": order.id, "ticket_id": ticket.id}


@pytest.fixture(scope="module")
def matrix_investigation(matrix_customer):
    """One real resolved investigation, built the same
    mocked-agent-boundary way `test_explainability.py::_resolve_via_chat`
    does, so the resource-dependent rows below (investigation detail,
    evidence, explanation, confidence) have a genuine row to check
    against rather than relying on a 404 short-circuit."""
    from unittest.mock import patch

    from app.db.models import Investigation, InvestigationStep, Ticket

    # A handful of other test files (test_analytics.py, test_kb_api.py)
    # call `db.query(Ticket).delete()` on this same shared file-based
    # test DB, but leave any `Investigation` row pointing at the deleted
    # ticket behind — a real, documented ROWID-reuse hazard (see
    # test_records_api.py's own note). A freshly `/api/chat`-created
    # Ticket can then legitimately reuse a low, now-free id that an
    # orphaned Investigation's `ticket_id` (UNIQUE) already claims.
    # Since nothing can legitimately still depend on an investigation
    # whose own ticket no longer exists, clearing those orphans first is
    # safe cleanup, not a destructive change to any other test's data.
    # `InvestigationStep.investigation_id` is NOT NULL, so the orphaned
    # steps must be deleted before their parent Investigation row — the
    # default relationship cascade tries to SET NULL there instead.
    cleanup_db = SessionLocal()
    real_ticket_ids = {row[0] for row in cleanup_db.query(Ticket.id).all()}
    orphan_ids = [
        inv.id for inv in cleanup_db.query(Investigation).all() if inv.ticket_id not in real_ticket_ids
    ]
    if orphan_ids:
        cleanup_db.query(InvestigationStep).filter(InvestigationStep.investigation_id.in_(orphan_ids)).delete(
            synchronize_session=False
        )
        cleanup_db.query(Investigation).filter(Investigation.id.in_(orphan_ids)).delete(synchronize_session=False)
        cleanup_db.commit()
    cleanup_db.close()

    with patch("app.orchestrator.classify", return_value=ClassificationResult(
        category="order", sentiment="neutral", urgency=3, reasoning="routine", confidence=0.8
    )):
        with patch("app.orchestrator.plan", return_value=PlanDecision(
            action="resolve", target_agent="order", reasoning="order can handle it"
        )):
            with patch("app.orchestrator.SPECIALISTS", {
                "order": lambda db, customer_id, message, channel="live_chat": SpecialistResponse(
                    reply="Your order is on its way.", used_tools=["get_customer_orders"], confidence=0.6,
                ),
                "technical": lambda db, customer_id, message, channel="live_chat": SpecialistResponse(reply="n/a"),
            }):
                with patch("app.orchestrator.verify", return_value=VerificationResult(approved=True, reasoning="grounded")):
                    with patch("app.orchestrator.critique", return_value=_MOCK_CRITIC_REVIEW):
                        with patch("app.orchestrator.extract_facts", return_value=[]):
                            resp = client.post("/api/chat", json={
                                "customer_id": matrix_customer["customer_id"], "message": "Where is my order?",
                            })
    assert resp.status_code == 200
    ticket_id = resp.json()["ticket_id"]

    db = SessionLocal()
    headers = staff_headers(db, "administrator")
    inv = client.get(f"/api/investigations/by-ticket/{ticket_id}", headers=headers)
    assert inv.status_code == 200
    return inv.json()["id"]


# --------------------------------------------------------------------- #
# Non-resource-dependent: permission checked with no row lookup at all,
# so any role's response reflects ONLY the permission gate.
# --------------------------------------------------------------------- #

NON_RESOURCE_MATRIX = [
    # Administrator's permission set is the real UNION of every other
    # role's (issue #199), so it legitimately holds view_own_tickets
    # too — it just has no real customer_id, so it gets a real empty
    # list rather than a 403 (see list_my_tickets()'s own docstring).
    ("/api/tickets/mine", {"customer", "administrator"}),
    ("/api/investigations", {"support_agent", "administrator"}),
    ("/api/investigations/metrics/agents", {"support_agent", "manager", "administrator"}),
    ("/api/analytics/summary", {"manager", "administrator"}),
    ("/api/escalations", {"support_agent", "manager", "administrator"}),
    ("/api/integrations/shopify/status", {"administrator"}),
    ("/api/users", {"administrator"}),
    ("/api/settings", {"administrator"}),
]


@pytest.mark.parametrize("path,allowed_roles", NON_RESOURCE_MATRIX)
def test_permission_gate_matrix(path, allowed_roles, matrix_customer):
    db = SessionLocal()
    for role in ALL_ROLES:
        headers = _headers_for(role, db, matrix_customer["customer_id"])
        resp = client.get(path, headers=headers)
        if role in allowed_roles:
            assert resp.status_code != 403, f"{role} should be allowed at {path}, got {resp.status_code}"
        else:
            assert resp.status_code == 403, f"{role} should be forbidden at {path}, got {resp.status_code}"


# --------------------------------------------------------------------- #
# Resource-dependent: the row genuinely exists, so a 403 vs. non-403
# response is a clean signal of the permission check alone.
# --------------------------------------------------------------------- #


def test_permission_gate_matrix_investigation_detail(matrix_customer, matrix_investigation):
    """`matrix_customer` genuinely owns `matrix_investigation`, so the
    "customer" role slot is also allowed here — a real, positive proof
    of #217's ownership rule, not just the staff-permission rule."""
    db = SessionLocal()
    allowed_roles = {"customer", "support_agent", "administrator"}
    for role in ALL_ROLES:
        headers = _headers_for(role, db, matrix_customer["customer_id"])
        resp = client.get(f"/api/investigations/{matrix_investigation}", headers=headers)
        if role in allowed_roles:
            assert resp.status_code == 200, f"{role} should see the investigation, got {resp.status_code}"
        else:
            assert resp.status_code == 403, f"{role} should be forbidden, got {resp.status_code}"


def test_permission_gate_matrix_explanation_and_confidence(matrix_customer, matrix_investigation):
    """[RBAC] issue #219's documented asymmetry: even the OWNING
    Customer cannot reach the full Explainability Panel data — only
    staff holding `view_explainability` (support_agent, administrator)
    can. Manager has neither `view_investigation_board` nor
    `view_explainability`, so is forbidden too."""
    db = SessionLocal()
    allowed_roles = {"support_agent", "administrator"}
    for role in ALL_ROLES:
        headers = _headers_for(role, db, matrix_customer["customer_id"])
        for suffix in ("explanation", "confidence"):
            resp = client.get(f"/api/investigations/{matrix_investigation}/{suffix}", headers=headers)
            if role in allowed_roles:
                assert resp.status_code == 200, f"{role} should see /{suffix}, got {resp.status_code}"
            else:
                assert resp.status_code == 403, f"{role} should be forbidden from /{suffix}, got {resp.status_code}"


def test_permission_gate_matrix_records(matrix_customer):
    """[RBAC] issue #218: staff with `view_evidence` (support_agent,
    administrator) can view ANY record; the owning Customer can view
    ONLY their own — proven here since `matrix_customer` IS the order's
    real owner. Manager holds neither `view_evidence` nor ownership, so
    stays forbidden."""
    db = SessionLocal()
    allowed_staff = {"support_agent", "administrator"}
    for role in ALL_ROLES:
        headers = _headers_for(role, db, matrix_customer["customer_id"])
        resp = client.get(f"/api/records/orders/{matrix_customer['order_id']}", headers=headers)
        if role in allowed_staff or role == "customer":
            assert resp.status_code == 200, f"{role} should see their own order, got {resp.status_code}"
        else:
            assert resp.status_code == 403, f"{role} should be forbidden, got {resp.status_code}"


def test_administrator_permission_set_is_the_real_union_of_every_other_role(matrix_customer, matrix_investigation):
    """[RBAC] issue #199 — Administrator's access is a computed UNION,
    not a hand-duplicated list: every endpoint reachable by ANY other
    staff role (or a Customer viewing their own data) must also be
    reachable by Administrator. Checked directly against ROLE_PERMISSIONS
    rather than re-deriving the union by hand here."""
    from app.auth.permissions import ROLE_PERMISSIONS
    from app.auth.roles import ADMINISTRATOR, CUSTOMER, MANAGER, SUPPORT_AGENT

    other_roles_union = (
        ROLE_PERMISSIONS[CUSTOMER] | ROLE_PERMISSIONS[SUPPORT_AGENT] | ROLE_PERMISSIONS[MANAGER]
    )
    assert other_roles_union.issubset(ROLE_PERMISSIONS[ADMINISTRATOR])

    # And a real, live confirmation: administrator can reach every
    # staff-gated surface in the matrix above.
    db = SessionLocal()
    headers = staff_headers(db, "administrator")
    for path, _ in NON_RESOURCE_MATRIX:
        resp = client.get(path, headers=headers)
        assert resp.status_code != 403, f"administrator should reach {path}, got {resp.status_code}"
