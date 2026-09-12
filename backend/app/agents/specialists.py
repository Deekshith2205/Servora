"""Specialist resolution agents. Billing implemented (issue #6). The other
three are still STUBS, each tracked by its own issue: "Implement Technical
Agent", "Implement Order Agent", "Implement Account Agent".

Rules for the real implementation (carried over from the architecture doc,
see docs/ARCHITECTURE.md):
  - Must call tools from app/tools/mock_tools.py (via
    app.tools.tool_registry.build_tool_registry) for any factual claim
    (order status, refund policy, account details) — never answer from
    model memory alone.
  - Must return a `used_tools` list so the reasoning trace in the Staff
    Dashboard can show exactly what was looked up.
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.llm import call_llm
from app.tools.tool_registry import build_tool_registry

# Tools that only *ground an answer* (look something up) rather than take an
# irreversible action. Used by _estimate_confidence — see its docstring.
_ACTION_TOOLS = {"issue_refund"}
_GROUNDING_TOOLS = {"get_customer", "get_customer_orders", "get_customer_tickets", "search_kb"}


@dataclass
class SpecialistResponse:
    reply: str
    used_tools: list[str] = field(default_factory=list)
    confidence: float = 0.0  # 0-1, consumed by the Verification/Escalation agents


def _estimate_confidence(used_tools: list[str]) -> float:
    """Confidence reflects what was actually grounded, not the model's tone.

    - An irreversible action tool (e.g. issue_refund) was called: the agent
      took concrete, verifiable action — 0.9.
    - No action tool, but at least one grounding tool (order lookup, KB
      search, ...) was called: the answer is grounded in real data but no
      action was taken — 0.6.
    - No tools called at all: nothing was verified against real data —
      0.2. This is deliberately low so the (future) Verification/Escalation
      agents catch an ungrounded reply instead of trusting it.
    """
    if any(t in _ACTION_TOOLS for t in used_tools):
        return 0.9
    if any(t in _GROUNDING_TOOLS for t in used_tools):
        return 0.6
    return 0.2


def _run_specialist(db: Session, system_prompt: str, message: str, max_tokens: int = 1500) -> SpecialistResponse:
    """Shared plumbing for a tool-calling specialist: wires the DB-bound
    tool registry into call_llm(), captures which tools were actually used,
    and derives a confidence score from that — so each specialist function
    only needs to supply its own system prompt.
    """
    tool_schemas, tool_handlers = build_tool_registry(db)
    used_tools: list[str] = []

    reply = call_llm(
        system_prompt=system_prompt,
        messages=[{"role": "user", "content": message}],
        tools=(tool_schemas, tool_handlers),
        tool_call_log=used_tools,
        max_tokens=max_tokens,
    )

    return SpecialistResponse(reply=reply, used_tools=used_tools, confidence=_estimate_confidence(used_tools))


_BILLING_SYSTEM_PROMPT = """You are the Billing specialist agent in an \
autonomous customer support pipeline. You handle billing and payment \
issues: duplicate charges, incorrect amounts, refund requests, and \
questions about a specific charge.

You must ground every factual claim (an order's amount, status, or the \
refund policy) in a tool call — never state one from memory alone.

Typical flow:
1. Call get_customer_orders to find the specific order the customer is \
referring to. If it is not obvious which order, ask a clarifying question \
in your reply instead of guessing.
2. Call search_kb (e.g. query "refund policy") to confirm a refund is \
warranted before acting.
3. Only if steps 1-2 support it, call issue_refund with the exact order \
ID. Never call issue_refund speculatively, more than once for the same \
order, or without first identifying the specific order.
4. Reply in plain, friendly language stating what you found and what \
action you took (or could not take, and why) — cite the specific order \
and policy, don't just say "I checked and it's fine."
"""


def resolve_billing(db: Session, customer_id: int, message: str) -> SpecialistResponse:
    return _run_specialist(db, _BILLING_SYSTEM_PROMPT, message)


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
