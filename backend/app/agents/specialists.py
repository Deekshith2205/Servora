"""Specialist resolution agents. All four implemented (issues #6-#9); tool
access locked down per-specialist in issue [P6] "Enforce specialist-specific
tool permissions".

Rules for the real implementation (carried over from the architecture doc,
see docs/ARCHITECTURE.md):
  - Must call tools from app/tools/mock_tools.py (via
    app.tools.tool_registry.build_filtered_tool_registry) for any factual
    claim (order status, refund policy, account details) — never answer
    from model memory alone.
  - Must return a `used_tools` list so the reasoning trace in the Staff
    Dashboard can show exactly what was looked up.
  - Each specialist only ever receives the tools
    app.tools.tool_registry.SPECIALIST_TOOL_PERMISSIONS allows it —
    enforced in code (see _run_specialist below), not left to the system
    prompt alone. The prompts below still describe each specialist's
    *intended* flow (which tool to call when, in what order) — that's
    still useful guidance for a well-behaved model — but the actual
    security boundary (e.g. "the Account specialist can never issue a
    refund") is real regardless of what any prompt says.
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.agents.memory import load_profile
from app.llm import call_llm
from app.tools.tool_registry import build_filtered_tool_registry

# Tools that only *ground an answer* (look something up) rather than take an
# irreversible action. Used by _estimate_confidence — see its docstring.
_ACTION_TOOLS = {"issue_refund"}
_GROUNDING_TOOLS = {"get_customer", "get_customer_orders", "get_customer_tickets", "search_kb", "check_payment_issue", "check_order_issue"}


@dataclass
class SpecialistResponse:
    reply: str
    used_tools: list[str] = field(default_factory=list)
    confidence: float = 0.0  # 0-1, consumed by the Verification/Escalation agents
    root_cause: str | None = None
    resolution: str | None = None
    # [FEATURE] Investigation Board: short, human-readable strings derived
    # from each tool call's REAL result (see _describe_evidence below) —
    # never placeholder text. Empty when no tools were called. Threaded
    # through to Investigation/InvestigationStep by orchestrator.py.
    evidence: list[str] = field(default_factory=list)
    # [EXPLAIN] issue #91: structured, id-addressable counterpart to
    # `evidence` above (`{type, ref_id, label}`) — same real tool results,
    # shaped so a frontend can deep-link to the actual order/customer/
    # ticket/KB-article row instead of only displaying a sentence. See
    # _describe_evidence_refs() below.
    evidence_refs: list[dict] = field(default_factory=list)


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


def _describe_evidence(tool_name: str, args: dict, result) -> str:
    """Turn one real tool call's (args, result) into a short, human-
    readable evidence string for the Investigation Board's Evidence
    Panel — [FEATURE] "AI Investigation Board". Deliberately derived
    from the ACTUAL SQLAlchemy objects / dicts mock_tools.py returns
    (never placeholder text): a customer's real name/tier, a real order
    ID, a real KB article title, the real detected issue_type. Falls
    back to a generic-but-still-real description for any future tool
    this isn't updated for, rather than raising.
    """
    if tool_name == "get_customer":
        if result is None:
            return f"Looked up customer #{args.get('customer_id')} — not found."
        return f"Retrieved customer profile: {result.name} ({result.tier} tier)."

    if tool_name == "get_customer_orders":
        if not result:
            return f"Queried orders for customer #{args.get('customer_id')} — none found."
        ids = ", ".join(f"#{o.id}" for o in result)
        return f"Retrieved {len(result)} order(s) for customer #{args.get('customer_id')}: {ids}."

    if tool_name == "get_customer_tickets":
        if not result:
            return f"Queried ticket history for customer #{args.get('customer_id')} — none found."
        return f"Retrieved {len(result)} prior ticket(s) for customer #{args.get('customer_id')}."

    if tool_name == "search_kb":
        if not result:
            return f"Searched knowledge base for {args.get('query')!r} — no matching articles."
        titles = "; ".join(a.title for a in result)
        return f"Searched knowledge base for {args.get('query')!r} — found: {titles}."

    if tool_name == "check_payment_issue":
        if isinstance(result, dict) and result.get("detected"):
            return f"Payment anomaly detected on order #{result.get('order_id')}: {result.get('issue_type')}."
        return f"Checked order #{args.get('order_id')} for payment anomalies — none detected."

    if tool_name == "check_order_issue":
        if isinstance(result, dict) and result.get("detected"):
            return f"Fulfillment anomaly detected on order #{result.get('order_id')}: {result.get('issue_type')}."
        return f"Checked order #{args.get('order_id')} for fulfillment anomalies — none detected."

    if tool_name == "issue_refund":
        if isinstance(result, dict) and result.get("success"):
            return f"Issued refund for order #{result.get('order_id')}."
        error = result.get("error") if isinstance(result, dict) else "unknown error"
        return f"Refund attempt for order #{args.get('order_id')} failed: {error}."

    return f"Called {tool_name} with {args}."


def _describe_evidence_refs(tool_name: str, args: dict, result) -> list[dict]:
    """[EXPLAIN] issue #91: structured counterpart to `_describe_evidence`
    above — zero or more `{type, ref_id, label}` dicts an "Evidence
    Explorer"/"Policy References" UI can deep-link to a real DB row.
    Derived from the exact same tool results (never a second lookup, never
    placeholder ids). Returns a list (not a single dict) because a tool
    like `get_customer_orders` can legitimately produce several refs from
    one call.

    Deliberate, documented scope limit (see issue #91): `KBArticle` has no
    section/paragraph granularity, so a `kb_article` ref always cites the
    whole article — not a sub-section.
    """
    if tool_name == "get_customer":
        if result is None:
            return []
        return [{"type": "customer", "ref_id": result.id, "label": result.name}]

    if tool_name == "get_customer_orders":
        return [{"type": "order", "ref_id": o.id, "label": f"Order #{o.id}"} for o in (result or [])]

    if tool_name == "get_customer_tickets":
        return [{"type": "ticket", "ref_id": t.id, "label": f"Ticket #{t.id}: {t.subject}"} for t in (result or [])]

    if tool_name == "search_kb":
        return [{"type": "kb_article", "ref_id": a.id, "label": a.title} for a in (result or [])]

    if tool_name in ("check_payment_issue", "check_order_issue"):
        if isinstance(result, dict) and result.get("order_id") is not None:
            return [{"type": "order", "ref_id": result["order_id"], "label": f"Order #{result['order_id']}"}]
        return []

    if tool_name == "issue_refund":
        if isinstance(result, dict) and result.get("order_id") is not None:
            return [{"type": "order", "ref_id": result["order_id"], "label": f"Refund on order #{result['order_id']}"}]
        return []

    return []


def _run_specialist(
    db: Session,
    system_prompt: str,
    customer_id: int,
    message: str,
    max_tokens: int = 1500,
    *,
    specialist: str,
) -> SpecialistResponse:
    """Shared plumbing for a tool-calling specialist: wires the DB-bound,
    PERMISSION-FILTERED tool registry into call_llm(), captures which
    tools were actually used, and derives a confidence score from that —
    so each specialist function only needs to supply its own system
    prompt (and its own name, for the permission lookup).

    ``specialist`` selects the allowlist from
    ``app.tools.tool_registry.SPECIALIST_TOOL_PERMISSIONS`` — this is the
    actual security boundary (issue [P6]): the tool schemas sent to the
    LLM and the handlers the tool-calling loop can execute are both
    filtered down to just that specialist's permitted tools before
    call_llm() ever runs, so a specialist that isn't "billing" cannot
    reach issue_refund no matter what its prompt says or what the model
    decides to try. Keyword-only so a call site can't accidentally pass
    the wrong positional string where `max_tokens` used to be.

    Also builds the user-facing message content: the customer's ID (so the
    model can actually call get_customer_orders/get_customer with the
    right ID — this was silently missing before issue #11 wired it in;
    every specialist was previously relying on the model to guess or ask,
    which a real API call would have surfaced immediately, and no session
    had a key to catch it) and, when issue #11's memory has anything on
    file, a short list of previously learned facts about this customer.
    """
    profile = load_profile(customer_id, db)
    tool_schemas, tool_handlers = build_filtered_tool_registry(db, specialist)
    used_tools: list[str] = []

    # [FEATURE] Investigation Board: capture one evidence string per real
    # tool call, on EVERY allowed tool (not just the two below that also
    # derive a root_cause) — applied first, innermost, so the
    # check_payment_issue/check_order_issue wraps below still see the
    # true tool result to reason about, while evidence is recorded
    # regardless of which specialist/tool ran.
    evidence: list[str] = []
    # [EXPLAIN] issue #91: structured counterpart to `evidence` above,
    # captured at the same point from the same real tool results.
    evidence_refs: list[dict] = []

    def _make_evidence_wrapper(name, fn):
        def wrapped(args):
            result = fn(args)
            evidence.append(_describe_evidence(name, args, result))
            evidence_refs.extend(_describe_evidence_refs(name, args, result))
            return result
        return wrapped

    tool_handlers = {name: _make_evidence_wrapper(name, fn) for name, fn in tool_handlers.items()}

    root_cause = None
    resolution = None

    original_check_payment = tool_handlers.get("check_payment_issue")
    if original_check_payment:
        def wrapped_check_payment(args):
            nonlocal root_cause
            res = original_check_payment(args)
            if res and isinstance(res, dict) and res.get("detected"):
                if res.get("issue_type") == "duplicate_payment":
                    root_cause = f"Duplicate payment detected for order {res.get('order_id')} against original order {res.get('related_order_id')}."
                elif res.get("issue_type") == "payment_fulfillment_mismatch":
                    root_cause = f"Payment succeeded but fulfillment failed for order {res.get('order_id')}."
            return res
        tool_handlers["check_payment_issue"] = wrapped_check_payment

    original_check_order = tool_handlers.get("check_order_issue")
    if original_check_order:
        def wrapped_check_order(args):
            nonlocal root_cause, resolution
            res = original_check_order(args)
            if res and isinstance(res, dict) and res.get("detected"):
                if res.get("issue_type") == "cancelled_order":
                    root_cause = "Order was cancelled."
                    resolution = "The order is cancelled and requires no further fulfillment processing."
                elif res.get("issue_type") == "inventory_shortfall":
                    root_cause = "Order fulfillment failed because inventory was unavailable."
                    resolution = "The order requires a fulfillment remedy or human review."
            return res
        tool_handlers["check_order_issue"] = wrapped_check_order

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

    return SpecialistResponse(
        reply=reply,
        used_tools=used_tools,
        confidence=_estimate_confidence(used_tools),
        root_cause=root_cause,
        resolution=resolution,
        evidence=evidence,
        evidence_refs=evidence_refs,
    )


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
    return _run_specialist(db, _BILLING_SYSTEM_PROMPT, customer_id, message, specialist="billing")


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
    return _run_specialist(db, _TECHNICAL_SYSTEM_PROMPT, customer_id, message, specialist="technical")


_ORDER_SYSTEM_PROMPT = """You are the Order specialist agent in an autonomous \
customer support pipeline. You handle questions about where an order is, \
shipping delays, cancellations, and lost packages.

You must ground every factual claim (an order's status, tracking info, or \
store policies) in a tool call — never state one from memory alone.

Typical flow:
1. Call get_customer_orders to find the specific order. Ask clarifying \
questions if the user's message is ambiguous.
2. Call check_order_issue BEFORE describing the order as merely delayed or \
processing. This will check for cancellations or inventory shortfalls.
3. If check_order_issue detects a cancelled order: explicitly explain the cancellation. \
Do NOT describe it as delayed or still processing. Do NOT attempt a refund here.
4. If check_order_issue detects an inventory shortfall: explicitly explain that fulfillment \
failed because the item was unavailable. Do NOT describe it as a normal shipping delay. \
Do NOT blindly issue a refund here.
5. If no anomaly is detected: use the order's status to answer the customer.
6. If an order is delayed (in "processing" or "shipped" for an unusually \
long time), call search_kb (e.g. query "shipping delay" or "discount") \
to find the exact policy for delayed orders, and if eligible, you may offer \
a courtesy discount (but do not issue a refund).
7. Reply in plain, friendly language explaining the exact status and \
what policy applies. Do not reveal hidden tool data.
"""


def resolve_order(db: Session, customer_id: int, message: str) -> SpecialistResponse:
    return _run_specialist(db, _ORDER_SYSTEM_PROMPT, customer_id, message, specialist="order")


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
    return _run_specialist(db, _ACCOUNT_SYSTEM_PROMPT, customer_id, message, specialist="account")


SPECIALISTS = {
    "billing": resolve_billing,
    "technical": resolve_technical,
    "order": resolve_order,
    "account": resolve_account,
}
