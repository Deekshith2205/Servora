"""Planner Agent. Implements issue #4 ("[P0] Implement Planner/Orchestrator
routing logic").

Given a ClassificationResult + this customer's known context, decides
exactly ONE of:
    "resolve"   -> route to the matching specialist agent
    "clarify"   -> ask the customer a follow-up question
    "escalate"  -> skip straight to the Escalation Agent

This is the piece that makes routing more than an if/else on category: the
decision is driven by an LLM call that weighs urgency, whether a specialist
can plausibly fix the issue, and this customer's recent ticket history —
NOT by sentiment alone. A calm, politely worded message about a serious or
repeated problem must still escalate; a frustrated-sounding but simple,
fixable request can still resolve.

CONTRACT CHANGE from the original stub: `plan()` now takes `customer_id`
and `db` in addition to `classification`, so it can look at ticket history
and (once implemented) the customer memory profile. `orchestrator.py` was
updated accordingly — see that file's one call site.
"""
from dataclasses import dataclass

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.classifier import ClassificationResult
from app.agents.memory import load_profile
from app.llm import call_llm
from app.tools import mock_tools

VALID_ACTIONS = ("resolve", "clarify", "escalate")
VALID_TARGETS = ("billing", "technical", "order", "account", "none")

SYSTEM_PROMPT = """You are the Planner Agent in an autonomous customer \
support pipeline. You receive a classified customer message plus what is \
known about this customer, and decide exactly one action:

- "resolve": route to a specialist agent (billing, technical, order, or \
account) who can plausibly fix this automatically. Set target_agent to \
that specialist.
- "clarify": the message is missing information a specialist would need \
(e.g. no order number, an ambiguous request) — ask a follow-up instead of \
guessing. Set target_agent to "none".
- "escalate": skip straight to a human agent. Set target_agent to "none".

Base the decision on what is actually at stake and whether it is fixable \
by an automated specialist — NOT on how the customer sounds. A calm, \
politely worded message about a serious, repeated, or clearly \
unresolvable problem (e.g. a customer calmly reporting their third failed \
delivery this month, or asking for a policy exception a specialist has no \
authority to grant) must still escalate. Conversely, a frustrated-sounding \
but simple, fixable request (e.g. an annoyed customer asking about a \
routine shipping delay) can still resolve.

Weigh, in order: (1) whether the customer's recent ticket history shows \
this same issue was already tried and failed — repeats should escalate \
rather than retry the same fix; (2) urgency; (3) whether the request is \
something one of the four specialists can actually act on with the tools \
available to them (order lookups, refunds, KB search — not, for example, \
legal disputes or requests outside company policy).

target_agent must be exactly one of: billing, technical, order, account, none.
reasoning must cite the specific signals that drove the decision (ticket \
history, urgency, fixability) — not just restate the action."""


@dataclass
class PlanDecision:
    action: str  # resolve | clarify | escalate
    target_agent: str  # billing | technical | order | account | none
    reasoning: str


class _PlanSchema(BaseModel):
    action: str = Field(description="One of: resolve, clarify, escalate")
    target_agent: str = Field(
        description="One of: billing, technical, order, account, none. "
        "'none' unless action is 'resolve'."
    )
    reasoning: str = Field(description="Why — cite the specific signals, not just the action")


def _summarize_recent_tickets(tickets: list) -> str:
    if not tickets:
        return "No prior tickets on file."
    lines = [
        f"- [{t.status}] {t.category}: {t.subject!r} (urgency {t.urgency}/10)"
        for t in tickets[-5:]
    ]
    return "\n".join(lines)


def plan(classification: ClassificationResult, customer_id: int, db: Session) -> PlanDecision:
    # `load_profile` returns {} today (issue: customer-memory not yet
    # implemented) — wiring it in now means no changes are needed here once
    # it is.
    profile = load_profile(customer_id)
    recent_tickets = mock_tools.get_customer_tickets(db, customer_id)

    context = (
        f"Category: {classification.category}\n"
        f"Sentiment: {classification.sentiment}\n"
        f"Urgency: {classification.urgency}/10\n"
        f"Classifier reasoning: {classification.reasoning}\n\n"
        f"Known customer profile: {profile or 'none recorded yet'}\n\n"
        f"Recent ticket history:\n{_summarize_recent_tickets(recent_tickets)}"
    )

    result = call_llm(
        system_prompt=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": context}],
        response_schema=_PlanSchema,
        max_tokens=500,
    )

    action = result.action if result.action in VALID_ACTIONS else "escalate"
    target_agent = result.target_agent if result.target_agent in VALID_TARGETS else "none"

    # Safety net: "resolve" without a real target agent is an invalid state —
    # fail safe to escalation rather than let the orchestrator's own fallback
    # (SPECIALISTS.get(..., technical)) silently guess a specialist.
    if action == "resolve" and target_agent == "none":
        action = "escalate"

    return PlanDecision(action=action, target_agent=target_agent, reasoning=result.reasoning)
