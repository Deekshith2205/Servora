"""Wires classify -> plan -> specialist -> verify -> memory into one call.

This already runs end-to-end today (against the stubs), so the frontend has
something real to hit from day one. As each agent issue lands, this file
should need minimal changes — mostly the stub bodies get replaced.

Issue #4 changed plan()'s signature (now takes customer_id and db, so it
can weigh ticket history) — updated the one call site below accordingly.

Issue #11 added the memory-write step (previously nothing called
memory.py at all) after a successful resolution — see _update_memory().
Deliberately best-effort: a failed extraction must never break the
customer-facing response, so LLMError is caught here rather than left to
propagate.

Issue #12 added a real HandoffPacket at both escalation points (a direct
Planner "escalate", or a failed Verification) — ChatResult gained a new
`handoff_packet` field (default None, so this is additive). Scope note:
this only makes the packet exist internally; exposing it through the
HTTP API is issue #13, and persisting it against a Ticket record for the
Staff Dashboard is issue #14.
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.agents.classifier import classify
from app.agents.escalation import HandoffPacket, build_handoff_packet
from app.agents.memory import extract_facts, merge_profile
from app.agents.planner import plan
from app.agents.specialists import SPECIALISTS
from app.agents.verification import verify
from app.llm import LLMError


@dataclass
class TraceStep:
    agent: str
    output: str


@dataclass
class ChatResult:
    reply: str
    status: str  # resolved | escalated
    trace: list[TraceStep] = field(default_factory=list)
    handoff_packet: HandoffPacket | None = None


def handle_message(db: Session, customer_id: int, message: str) -> ChatResult:
    trace: list[TraceStep] = []

    classification = classify(message)
    trace.append(TraceStep("classifier", classification.reasoning))

    decision = plan(classification, customer_id, db)
    trace.append(TraceStep("planner", decision.reasoning))

    if decision.action == "escalate":
        packet = build_handoff_packet(
            message=message,
            attempted_fixes=[step.output for step in trace],
            urgency=classification.urgency,
        )
        trace.append(TraceStep("escalation", f"Routed straight to a human agent — {packet.root_cause_hypothesis}"))
        return ChatResult(
            reply="A human agent will follow up shortly.", status="escalated", trace=trace, handoff_packet=packet
        )

    specialist_fn = SPECIALISTS.get(decision.target_agent, SPECIALISTS["technical"])
    response = specialist_fn(db, customer_id, message)
    trace.append(TraceStep(f"{decision.target_agent}_specialist", response.reply))

    verification = verify(response)
    trace.append(TraceStep("verification", verification.reasoning))

    if not verification.approved:
        packet = build_handoff_packet(
            message=message,
            attempted_fixes=[step.output for step in trace],
            urgency=classification.urgency,
            confidence=response.confidence,
        )
        trace.append(
            TraceStep("escalation", f"Verification failed — escalating to a human agent — {packet.root_cause_hypothesis}")
        )
        return ChatResult(
            reply="A human agent will follow up shortly.", status="escalated", trace=trace, handoff_packet=packet
        )

    _update_memory(customer_id, message, response.reply, db, trace)

    return ChatResult(reply=response.reply, status="resolved", trace=trace)


def _update_memory(customer_id: int, message: str, reply: str, db: Session, trace: list[TraceStep]) -> None:
    """Best-effort: extraction failures must never break the customer's
    response — they're logged in the trace instead of raised."""
    try:
        facts = extract_facts(message, reply)
    except LLMError as exc:
        trace.append(TraceStep("memory", f"Skipped — fact extraction failed: {exc}"))
        return

    merge_profile(customer_id, facts, db)
    trace.append(
        TraceStep("memory", f"Learned: {facts}" if facts else "Nothing new worth remembering from this turn.")
    )
