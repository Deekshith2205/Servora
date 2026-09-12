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
`handoff_packet` field (default None, so this is additive). Issue #13
exposed that through the HTTP API and the frontend chat bubble.

Issue #14 persists the trace + packet against a real Ticket row (see
_create_escalation_ticket()) whenever a conversation escalates, so it
shows up in the Staff Dashboard's queue with full detail — previously
/api/chat never created or touched a Ticket at all; the dashboard only
ever showed the seeded demo tickets. ChatResult gained a `ticket_id`
field (default None, additive) so the frontend can link straight to the
new ticket if useful.
"""
import json
from dataclasses import asdict, dataclass, field

from sqlalchemy.orm import Session

from app.agents.classifier import ClassificationResult, classify
from app.agents.escalation import HandoffPacket, build_handoff_packet
from app.agents.memory import extract_facts, merge_profile
from app.agents.planner import plan
from app.agents.specialists import SPECIALISTS
from app.agents.verification import verify
from app.db.models import Ticket
from app.llm import LLMError

_SUBJECT_MAX_LEN = 80


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
    ticket_id: int | None = None


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
        ticket_id = _create_ticket(db, customer_id, message, classification, trace, "escalated", packet)
        return ChatResult(
            reply="A human agent will follow up shortly.",
            status="escalated",
            trace=trace,
            handoff_packet=packet,
            ticket_id=ticket_id,
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
        ticket_id = _create_ticket(db, customer_id, message, classification, trace, "escalated", packet)
        return ChatResult(
            reply="A human agent will follow up shortly.",
            status="escalated",
            trace=trace,
            handoff_packet=packet,
            ticket_id=ticket_id,
        )

    _update_memory(customer_id, message, response.reply, db, trace)

    ticket_id = _create_ticket(db, customer_id, message, classification, trace, "resolved")
    return ChatResult(reply=response.reply, status="resolved", trace=trace, ticket_id=ticket_id)


def _create_ticket(
    db: Session,
    customer_id: int,
    message: str,
    classification: ClassificationResult,
    trace: list[TraceStep],
    status: str,
    packet: HandoffPacket | None = None,
) -> int:
    """Persists a Ticket row so this escalation shows up in the Staff
    Dashboard's queue (GET /api/escalations) with its full trace and
    handoff packet attached (GET /api/escalations/{id})."""
    subject = message if len(message) <= _SUBJECT_MAX_LEN else message[: _SUBJECT_MAX_LEN - 1] + "…"

    ticket = Ticket(
        customer_id=customer_id,
        category=classification.category,
        subject=subject,
        message=message,
        sentiment=classification.sentiment,
        urgency=classification.urgency,
        status=status,
        confidence=classification.confidence,
        trace_json=json.dumps([asdict(step) for step in trace]),
        handoff_packet_json=json.dumps(asdict(packet)) if packet else None,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket.id


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
