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
from dataclasses import dataclass, field

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
history, urgency, fixability) — not just restate the action.

alternatives_considered: list the OTHER 1-2 actions from resolve/clarify/ \
escalate that you did NOT choose, each with a specific one-line reason you \
rejected it (cite the same kind of signal as your reasoning — e.g. "escalate \
— not needed, the specialist can resolve this with a standard refund" or \
"clarify — the order was unambiguous, no need to ask"). Never list the \
action you actually chose as one of its own alternatives, and never give a \
generic reason like "didn't fit" — this is shown to a human reviewer as \
evidence of what you actually weighed, not just what you concluded."""


@dataclass
class Alternative:
    action: str  # resolve | clarify | escalate
    rejected_because: str


@dataclass
class PlanDecision:
    action: str  # resolve | clarify | escalate
    target_agent: str  # billing | technical | order | account | none
    reasoning: str
    # [EXPLAIN] issue #89: the actions NOT chosen and why — see the system
    # prompt above. Defaults to empty rather than fabricated content when
    # the LLM path isn't taken (e.g. a future deterministic fallback).
    alternatives_considered: list[Alternative] = field(default_factory=list)


class _AlternativeSchema(BaseModel):
    action: str = Field(description="One of: resolve, clarify, escalate — an action NOT chosen")
    rejected_because: str = Field(description="Specific, one-line reason this action was rejected")


class _PlanSchema(BaseModel):
    action: str = Field(description="One of: resolve, clarify, escalate")
    target_agent: str = Field(
        description="One of: billing, technical, order, account, none. "
        "'none' unless action is 'resolve'."
    )
    reasoning: str = Field(description="Why — cite the specific signals, not just the action")
    alternatives_considered: list[_AlternativeSchema] = Field(
        default_factory=list,
        description="The 1-2 actions NOT chosen and a specific reason each was rejected.",
    )


def _summarize_recent_tickets(tickets: list) -> str:
    if not tickets:
        return "No prior tickets on file."
    lines = [
        f"- [{t.status}] {t.category}: {t.subject!r} (urgency {t.urgency}/10)"
        for t in tickets[-5:]
    ]
    return "\n".join(lines)


def plan(classification: ClassificationResult, customer_id: int, db: Session) -> PlanDecision:
    # load_profile is real now (issue #11) — gained a `db` param, see
    # memory.py's module docstring for why.
    profile = load_profile(customer_id, db)
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

    # [EXPLAIN] issue #89: keep only alternatives that are actually valid
    # AND distinct from the chosen action — defensive against the LLM
    # naming an invalid action or (contradictorily) listing its own choice
    # as something it rejected, same fail-safe spirit as the action/target
    # validation above.
    alternatives = [
        Alternative(action=a.action, rejected_because=a.rejected_because)
        for a in getattr(result, "alternatives_considered", [])
        if a.action in VALID_ACTIONS and a.action != action
    ]

    return PlanDecision(
        action=action,
        target_agent=target_agent,
        reasoning=result.reasoning,
        alternatives_considered=alternatives,
    )
