"""Specialist resolution agents — STUBS. Each is tracked by its own issue:
"Implement Billing Agent", "Implement Technical Agent", "Implement Order
Agent", "Implement Account Agent".

Rules for the real implementation (carried over from the architecture doc,
see docs/ARCHITECTURE.md):
  - Must call tools from app/tools/mock_tools.py for any factual claim
    (order status, refund policy, account details) — never answer from
    model memory alone.
  - Must return a `used_tools` list so the reasoning trace in the Staff
    Dashboard can show exactly what was looked up.
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session


@dataclass
class SpecialistResponse:
    reply: str
    used_tools: list[str] = field(default_factory=list)
    confidence: float = 0.0  # 0-1, consumed by the Verification/Escalation agents


def resolve_billing(db: Session, customer_id: int, message: str) -> SpecialistResponse:
    # TODO(issue: billing-agent): real implementation using mock_tools.issue_refund / search_kb
    return SpecialistResponse(reply="STUB: billing agent not implemented yet.", confidence=0.0)


def resolve_technical(db: Session, customer_id: int, message: str) -> SpecialistResponse:
    # TODO(issue: technical-agent)
    return SpecialistResponse(reply="STUB: technical agent not implemented yet.", confidence=0.0)


def resolve_order(db: Session, customer_id: int, message: str) -> SpecialistResponse:
    # TODO(issue: order-agent): real implementation using mock_tools.get_customer_orders
    return SpecialistResponse(reply="STUB: order agent not implemented yet.", confidence=0.0)


def resolve_account(db: Session, customer_id: int, message: str) -> SpecialistResponse:
    # TODO(issue: account-agent)
    return SpecialistResponse(reply="STUB: account agent not implemented yet.", confidence=0.0)


SPECIALISTS = {
    "billing": resolve_billing,
    "technical": resolve_technical,
    "order": resolve_order,
    "account": resolve_account,
}
