"""Specialist resolution agents. All four implemented (issues #6-#9).

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

from app.agents.memory import load_profile
from app.llm import call_llm
from app.tools.tool_registry import build_tool_registry

# Tools that only *ground an answer* (look something up) rather than take an
# irreversible action. Used by _estimate_confidence — see its docstring.
_ACTION_TOOLS = {"issue_refund"}
_GROUNDING_TOOLS = {"get_customer", "get_customer_orders", "get_customer_tickets", "search_kb", "check_payment_issue"}


@dataclass
class SpecialistResponse:
    reply: str
    used_tools: list[str] = field(default_factory=list)
    confidence: float = 0.0  # 0-1, consumed by the Verification/Escalation agents
    root_cause: str | None = None


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


def _run_specialist(
    db: Session, system_prompt: str, customer_id: int, message: str, max_tokens: int = 1500
) -> SpecialistResponse:
    """Shared plumbing for a tool-calling specialist: wires the DB-bound
    tool registry into call_llm(), captures which tools were actually used,
    and derives a confidence score from that — so each specialist function
    only needs to supply its own system prompt.

    Also builds the user-facing message content: the customer's ID (so the
    model can actually call get_customer_orders/get_customer with the
    right ID — this was silently missing before issue #11 wired it in;
    every specialist was previously relying on the model to guess or ask,
    which a real API call would have surfaced immediately, and no session
    had a key to catch it) and, when issue #11's memory has anything on
    file, a short list of previously learned facts about this customer.
    """
    profile = load_profile(customer_id, db)
    tool_schemas, tool_handlers = build_tool_registry(db)
    used_tools: list[str] = []
    
    root_cause = None
    original_check = tool_handlers.get("check_payment_issue")
    if original_check:
        def wrapped_check(args):
            nonlocal root_cause
            res = original_check(args)
            if res and isinstance(res, dict) and res.get("detected"):
                if res.get("issue_type") == "duplicate_payment":
                    root_cause = f"Duplicate payment detected for order {res.get('order_id')} against original order {res.get('related_order_id')}."
                elif res.get("issue_type") == "payment_fulfillment_mismatch":
                    root_cause = f"Payment succeeded but fulfillment failed for order {res.get('order_id')}."
            return res
        tool_handlers["check_payment_issue"] = wrapped_check

    context_lines = [f"Customer ID: {customer_id}"]
    if profile.get("facts"):
        context_lines.append("Known facts about this customer from past interactions: " + "; ".join(profile["facts"]))
    context_lines.append(f"Customer message: {message}")

    reply = call_llm(
        system_prompt=system_prompt,
        messages=[{"role": "user", "content": "\n".join(context_lines)}],
        tools=(tool_schemas, tool_handlers),
        tool_call_log=used_tools,
        max_tokens=max_tokens,
    )

    return SpecialistResponse(reply=reply, used_tools=used_tools, confidence=_estimate_confidence(used_tools), root_cause=root_cause)


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
2. Call check_payment_issue to deterministically check for payment anomalies \
(duplicate payments or payment/fulfillment mismatches) BEFORE deciding to refund.
3. If check_payment_issue detects a duplicate_payment: \
refund ONLY the duplicate order if policy allows. Do not refund the original order. \
Never refund the duplicate more than once.
4. If check_payment_issue detects a payment_fulfillment_mismatch: \
recognize that the payment succeeded but fulfillment failed. DO NOT treat \
this as an ordinary refund request. Follow an appropriate escalation or remedy path \
instead of refunding it blindly as a duplicate.
5. If no anomaly is detected (normal refund request), call search_kb to confirm \
a refund is warranted before acting.
6. Only if steps 1-5 support it, call issue_refund with the exact order \
ID. Never call issue_refund speculatively, more than once for the same \
order, or without first identifying the specific order.
7. Reply in plain, friendly language stating what you found and what \
action you took (or could not take, and why) — cite the specific order \
and policy, don't just say "I checked and it's fine."
"""


def resolve_billing(db: Session, customer_id: int, message: str) -> SpecialistResponse:
    return _run_specialist(db, _BILLING_SYSTEM_PROMPT, customer_id, message)


_TECHNICAL_SYSTEM_PROMPT = """You are the Technical specialist agent in an \
autonomous customer support pipeline. You handle product/app technical \
issues: bugs, crashes, errors, and "how do I..." troubleshooting \
questions. You have no ability to take an action (no refunds, no account \
changes) — your job is to ground an answer in real documentation, not to \
fix anything.

You must ground every troubleshooting claim in a tool call — never invent \
a fix from memory.

Typical flow:
1. Call search_kb with keywords from the customer's issue to find a \
relevant troubleshooting article.
2. Optionally call get_customer_tickets to check whether this customer has \
reported the same or a related issue before — a repeat, unresolved issue \
is worth naming explicitly in your reply, since it matters for escalation.
3. If a relevant KB article is found, walk the customer through it in your \
reply, citing it directly.
4. If no relevant KB article is found, say so honestly and suggest the \
issue may need a human agent — do NOT guess at a fix that isn't grounded \
in what search_kb actually returned.
"""


def resolve_technical(db: Session, customer_id: int, message: str) -> SpecialistResponse:
    return _run_specialist(db, _TECHNICAL_SYSTEM_PROMPT, customer_id, message)


_ORDER_SYSTEM_PROMPT = """You are the Order specialist agent in an \
autonomous customer support pipeline. You handle order status, delivery, \
and shipping-delay questions.

You must ground every claim about an order's status or timing in a tool \
call — never state one from memory alone.

Typical flow:
1. Call get_customer_orders to find the order(s) the customer means.
2. If an order looks delayed (still "processing" well past when it should \
have shipped, or the customer describes an unusually long wait), call \
search_kb (e.g. query "order delays") to check the delay policy. If the \
order qualifies, PROACTIVELY mention the courtesy discount in your reply \
— do not wait for the customer to ask for it.
3. Reply citing the specific order's status and, when applicable, the \
delay policy.

Important limitation: you do NOT have a tool that actually issues a \
discount code. When a discount applies, tell the customer they are \
eligible and that it will be applied/sent to them — never claim you have \
already applied a discount, since that would not be true.
"""


def resolve_order(db: Session, customer_id: int, message: str) -> SpecialistResponse:
    return _run_specialist(db, _ORDER_SYSTEM_PROMPT, customer_id, message)


_ACCOUNT_SYSTEM_PROMPT = """You are the Account specialist agent in an \
autonomous customer support pipeline. You handle profile/account-detail \
questions (name, email, phone, tier) and are READ-ONLY — you cannot reset \
a password or change any account detail (there is no tool for that yet).

You must ground every claim about the account in a tool call — never \
state one from memory alone.

Typical flow:
1. Call get_customer to look up the account.
2. Reply with the requested information, citing what get_customer \
returned.
3. If the customer asks for something you cannot do (reset a password, \
change an email, close an account), say so plainly and note a human agent \
can help with that — do not attempt it and do not refuse without \
explanation.
"""


def resolve_account(db: Session, customer_id: int, message: str) -> SpecialistResponse:
    return _run_specialist(db, _ACCOUNT_SYSTEM_PROMPT, customer_id, message)


SPECIALISTS = {
    "billing": resolve_billing,
    "technical": resolve_technical,
    "order": resolve_order,
    "account": resolve_account,
}
