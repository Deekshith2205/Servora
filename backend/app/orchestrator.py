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

[FEATURE] Investigation Board: alongside the existing `Ticket.trace_json`
snapshot (unchanged, still written exactly as before), each run of this
pipeline ALSO persists a normalized `Investigation` + `InvestigationStep`
row set (see `_persist_investigation()` and `app/db/models.py`'s
docstrings for why a separate, queryable table rather than parsing JSON
harder). This hooks into the SAME points `trace.append()` already does,
timing each stage and collecting the same data already being computed
(classification, plan, specialist response, verification, handoff
packet) — it does not change what any agent computes or how the
existing trace/Ticket persistence works.
"""
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.agents.classifier import ClassificationResult, classify
from app.agents.escalation import HandoffPacket, build_handoff_packet
from app.agents.memory import extract_facts, merge_profile
from app.agents.planner import plan
from app.agents.specialists import SPECIALISTS
from app.agents.verification import verify
from app.db.models import Investigation, InvestigationStep, Ticket
from app.llm import LLMError
from app.services import stream_bus

_SUBJECT_MAX_LEN = 80


@dataclass
class TraceStep:
    agent: str
    output: str
    confidence: float | None = None
    root_cause: str | None = None
    resolution: str | None = None


@dataclass
class ChatResult:
    reply: str
    status: str  # resolved | escalated
    trace: list[TraceStep] = field(default_factory=list)
    handoff_packet: HandoffPacket | None = None
    ticket_id: int | None = None


def handle_message(db: Session, customer_id: int, message: str, stream_key: str | None = None) -> ChatResult:
    """`stream_key` — [SWARM] issue #79, additive/optional: when the
    caller (see app/api/chat.py) supplies one, every `_record()` call
    below ALSO publishes a real-time event to `stream_bus`, keyed by that
    string, as that stage actually completes — not a replay after the
    fact. `None` (the default) reproduces the exact previous behavior for
    every existing caller (tests included): nothing is published, nothing
    changes.
    """
    trace: list[TraceStep] = []
    # [FEATURE] Investigation Board: one dict per trace step, timed and
    # evidence-carrying — persisted as InvestigationStep rows at the end
    # by _persist_investigation(). Kept as a plain parallel list (not
    # folded into TraceStep itself) so the existing trace/Ticket.trace_json
    # contract stays byte-for-byte unchanged for every existing caller.
    step_records: list[dict] = []
    investigation_started_at = datetime.utcnow()

    def _record(agent: str, output: str, *, action: str, status: str = "completed",
                evidence: list[str] | None = None, duration_ms: int = 0,
                confidence: float | None = None, root_cause: str | None = None,
                resolution: str | None = None, started_at: datetime | None = None,
                used_tools: list[str] | None = None, alternatives: list | None = None,
                evidence_refs: list[dict] | None = None) -> None:
        trace.append(TraceStep(agent, output, confidence=confidence, root_cause=root_cause, resolution=resolution))
        step_records.append({
            "agent_name": agent,
            "action": action,
            "status": status,
            "evidence": evidence or [],
            "duration_ms": duration_ms,
            "confidence": confidence,
            # [SWARM] issue #77: real wall-clock start (falls back to "now"
            # if a call site forgets to pass one, rather than leaving a
            # required DB column null).
            "started_at": started_at or datetime.utcnow(),
            # [SWARM] issue #77: the fuller reasoning text — previously
            # only the short `action` label reached InvestigationStep.
            "reasoning_text": output,
            # [SWARM] issue #77 / [EXPLAIN] #89/#91: additive, all default
            # to empty so most steps (classifier, verification, memory)
            # simply record nothing here.
            "used_tools": used_tools or [],
            "alternatives": [asdict(a) for a in (alternatives or [])],
            "evidence_refs": evidence_refs or [],
        })
        # [SWARM] issue #79: real-time push, same shape a step_records
        # entry has (minus the pieces only meaningful once persisted, like
        # a DB-assigned step_number — the frontend uses list position for
        # that, same as it already does for the replay-based Swarm view).
        if stream_key:
            stream_bus.publish(stream_key, {
                "type": "step",
                "step_number": len(step_records),
                "agent_name": agent,
                "action": action,
                "status": status,
                "confidence": confidence,
                "duration_ms": duration_ms,
            })

    def _finish(ticket_id: int, investigation_id: int) -> None:
        """[SWARM] issue #79: the stream's final event — carries the real,
        now-persisted ticket_id/investigation_id so the frontend can hand
        off from "live" to fetching the completed record normally (same
        data GET /api/investigations/{id} would return)."""
        if stream_key:
            stream_bus.publish(stream_key, {"type": "done", "ticket_id": ticket_id, "investigation_id": investigation_id})

    try:
        t0, t0_wall = time.perf_counter(), datetime.utcnow()
        classification = classify(message)
        _record(
            "classifier", classification.reasoning,
            action=f"Classified issue as {classification.category} (urgency {classification.urgency}/10)",
            duration_ms=round((time.perf_counter() - t0) * 1000),
            confidence=classification.confidence, started_at=t0_wall,
        )

        t0, t0_wall = time.perf_counter(), datetime.utcnow()
        decision = plan(classification, customer_id, db)
        plan_action = (
            f"Decided to resolve via the {decision.target_agent} specialist"
            if decision.action == "resolve"
            else f"Decided to {decision.action}"
        )
        _record(
            "planner", decision.reasoning, action=plan_action,
            duration_ms=round((time.perf_counter() - t0) * 1000), started_at=t0_wall,
            # [EXPLAIN] issue #89: the actions NOT chosen, straight from the
            # Planner's own structured output — see planner.py.
            alternatives=decision.alternatives_considered,
        )

        if decision.action == "escalate":
            t0, t0_wall = time.perf_counter(), datetime.utcnow()
            packet = build_handoff_packet(
                message=message,
                attempted_fixes=[step.output for step in trace],
                urgency=classification.urgency,
            )
            _record(
                "escalation", f"Routed straight to a human agent — {packet.root_cause_hypothesis}",
                action="Routed directly to a human agent",
                evidence=[packet.situation, packet.root_cause_hypothesis],
                duration_ms=round((time.perf_counter() - t0) * 1000), started_at=t0_wall,
            )
            ticket_id = _create_ticket(db, customer_id, message, classification, trace, "escalated", packet)
            investigation_id = _persist_investigation(
                db, ticket_id, customer_id, investigation_started_at, step_records,
                status="escalated", root_cause=packet.root_cause_hypothesis,
                resolution=packet.recommended_action, confidence=classification.confidence,
            )
            _finish(ticket_id, investigation_id)
            return ChatResult(
                reply="A human agent will follow up shortly.",
                status="escalated",
                trace=trace,
                handoff_packet=packet,
                ticket_id=ticket_id,
            )

        t0, t0_wall = time.perf_counter(), datetime.utcnow()
        specialist_fn = SPECIALISTS.get(decision.target_agent, SPECIALISTS["technical"])
        response = specialist_fn(db, customer_id, message)

        # Extract root_cause safely if it was populated by the specialist
        root_cause = getattr(response, "root_cause", None)
        resolution = getattr(response, "resolution", None)
        _record(
            f"{decision.target_agent}_specialist", response.reply,
            action=root_cause or f"{decision.target_agent.title()} specialist investigated and responded",
            evidence=getattr(response, "evidence", []),
            duration_ms=round((time.perf_counter() - t0) * 1000), started_at=t0_wall,
            confidence=response.confidence, root_cause=root_cause, resolution=resolution,
            # [SWARM] issue #77 / [EXPLAIN] #91: the tools actually called and
            # their structured, id-addressable evidence refs.
            used_tools=getattr(response, "used_tools", []),
            evidence_refs=getattr(response, "evidence_refs", []),
        )

        t0, t0_wall = time.perf_counter(), datetime.utcnow()
        verification = verify(response)
        _record(
            "verification", verification.reasoning,
            action="Verified the proposed resolution" if verification.approved else "Verification failed",
            status="completed" if verification.approved else "failed",
            duration_ms=round((time.perf_counter() - t0) * 1000), started_at=t0_wall,
        )

        if not verification.approved:
            t0, t0_wall = time.perf_counter(), datetime.utcnow()
            packet = build_handoff_packet(
                message=message,
                attempted_fixes=[step.output for step in trace],
                urgency=classification.urgency,
                confidence=response.confidence,
            )
            _record(
                "escalation", f"Verification failed — escalating to a human agent — {packet.root_cause_hypothesis}",
                action="Escalated after failed verification",
                evidence=[packet.situation, packet.root_cause_hypothesis],
                duration_ms=round((time.perf_counter() - t0) * 1000), started_at=t0_wall,
            )
            ticket_id = _create_ticket(db, customer_id, message, classification, trace, "escalated", packet)
            investigation_id = _persist_investigation(
                db, ticket_id, customer_id, investigation_started_at, step_records,
                status="escalated", root_cause=packet.root_cause_hypothesis,
                resolution=packet.recommended_action, confidence=response.confidence,
            )
            _finish(ticket_id, investigation_id)
            return ChatResult(
                reply="A human agent will follow up shortly.",
                status="escalated",
                trace=trace,
                handoff_packet=packet,
                ticket_id=ticket_id,
            )

        t0, t0_wall = time.perf_counter(), datetime.utcnow()
        _update_memory(customer_id, message, response.reply, db, trace)
        memory_step = trace[-1]
        step_records.append({
            "agent_name": memory_step.agent,
            "action": memory_step.output,
            "status": "completed",
            "evidence": [],
            "evidence_refs": [],
            "duration_ms": round((time.perf_counter() - t0) * 1000),
            "confidence": None,
            "started_at": t0_wall,
            "reasoning_text": memory_step.output,
            "used_tools": [],
            "alternatives": [],
        })
        if stream_key:
            stream_bus.publish(stream_key, {
                "type": "step", "step_number": len(step_records), "agent_name": memory_step.agent,
                "action": memory_step.output, "status": "completed", "confidence": None, "duration_ms": step_records[-1]["duration_ms"],
            })

        ticket_id = _create_ticket(db, customer_id, message, classification, trace, "resolved")
        investigation_id = _persist_investigation(
            db, ticket_id, customer_id, investigation_started_at, step_records,
            status="resolved", root_cause=root_cause, resolution=resolution or response.reply,
            confidence=response.confidence,
        )
        _finish(ticket_id, investigation_id)
        return ChatResult(reply=response.reply, status="resolved", trace=trace, ticket_id=ticket_id)
    finally:
        # [SWARM] issue #79: unconditionally send the "no more events"
        # sentinel — on a normal return, `_finish()` above already
        # published the real "done" event with the ticket/investigation
        # id; this is the separate signal that tells the SSE generator to
        # stop reading and close the connection. On an exception (e.g. an
        # LLMError propagating to app/api/chat.py's own 502 handler),
        # `_finish()` never ran, so this is the ONLY signal the stream
        # gets — without it, that SSE connection would hang open until
        # its own idle timeout instead of closing promptly. The
        # customer-facing error itself still surfaces normally through
        # chat.py's existing HTTPException handling — this only affects
        # the live Swarm view, which simply stops updating.
        if stream_key:
            stream_bus.close(stream_key)


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


def _persist_investigation(
    db: Session,
    ticket_id: int,
    customer_id: int,
    started_at: datetime,
    step_records: list[dict],
    *,
    status: str,
    root_cause: str | None,
    resolution: str | None,
    confidence: float | None,
) -> int:
    """[FEATURE] Investigation Board: persists the normalized
    Investigation + InvestigationStep rows for this pipeline run,
    alongside (not instead of) the Ticket.trace_json snapshot
    _create_ticket() already wrote. See app/db/models.py's Investigation
    docstring for why this is a separate table.

    Called at every point handle_message() returns (both escalation
    paths and the resolved path) — mirrors _create_ticket()'s call sites
    exactly, since an Investigation always maps 1:1 to the Ticket just
    created.

    Returns the new Investigation's id — [SWARM] issue #79 threads this
    into the stream's final "done" event so a live-mode frontend can hand
    off to fetching the completed record normally, without a second
    round-trip through GET /api/investigations/by-ticket/{ticket_id}.
    """
    investigation = Investigation(
        ticket_id=ticket_id,
        customer_id=customer_id,
        started_at=started_at,
        completed_at=datetime.utcnow(),
        confidence_score=confidence,
        root_cause=root_cause,
        resolution=resolution,
        status=status,
    )
    db.add(investigation)
    db.flush()  # assigns investigation.id without a second round-trip commit

    for i, rec in enumerate(step_records, start=1):
        db.add(InvestigationStep(
            investigation_id=investigation.id,
            step_number=i,
            timestamp=datetime.utcnow(),
            # [SWARM] issue #77: real wall-clock start, distinct from
            # `timestamp` above (which marks completion) — `.get(...)`
            # rather than a bare index since not every historical
            # step_records dict is guaranteed to carry every new key.
            started_at=rec.get("started_at"),
            agent_name=rec["agent_name"],
            action=rec["action"],
            status=rec["status"],
            reasoning_text=rec.get("reasoning_text"),
            evidence_json=json.dumps(rec["evidence"]),
            evidence_refs_json=json.dumps(rec.get("evidence_refs", [])),
            used_tools_json=json.dumps(rec.get("used_tools", [])),
            alternatives_json=json.dumps(rec.get("alternatives", [])),
            # [SWARM] issue #78: explicit dependency, not just an
            # assumption the graph API makes from step order. Today's
            # pipeline never fans out — every step causally depends on
            # exactly the one immediately before it, for every branch
            # (a direct-Planner escalation is a shorter chain, not a
            # differently-shaped one) — so this is genuinely correct,
            # not just convenient, per step_number alone.
            depends_on_json=json.dumps([i - 1] if i > 1 else []),
            duration_ms=rec["duration_ms"],
            confidence=rec["confidence"],
        ))
    db.commit()
    return investigation.id


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
