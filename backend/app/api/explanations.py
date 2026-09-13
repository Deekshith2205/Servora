"""[EXPLAIN] issue #92: explanation / evidence / confidence read APIs.

Built entirely on the existing Investigation/InvestigationStep tables (see
app/db/models.py, and the [SWARM] #77 / [EXPLAIN] #89-#91 columns those
issues add) plus, for an escalated investigation's decision rationale, the
Ticket row's handoff_packet_json (app/orchestrator.py::_create_ticket()).
No new storage, no new LLM call — `decision_rationale` is a deterministic
composition over data already computed, per issue #92's explicit design
choice (an extra network call isn't needed just to format text that
already exists).

Deliberately does NOT duplicate GET /api/investigations/{id} three times —
these three endpoints are each a narrower view over the exact same source
data, kept consistent by construction (one builder per concern, reused
across endpoints) rather than by convention.
"""
import json
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import (
    ConfidenceBreakdownOut,
    ConfidenceOut,
    EvidenceOut,
    ExplanationOut,
    InvestigationAgentSummaryOut,
)
from app.db.database import get_db
from app.db.models import Investigation, Ticket

router = APIRouter(prefix="/api/investigations", tags=["explanations"])


def _get_investigation(investigation_id: int, db: Session) -> Investigation:
    investigation = db.get(Investigation, investigation_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail=f"Investigation {investigation_id} not found")
    return investigation


def _agents_consulted(investigation: Investigation) -> list[InvestigationAgentSummaryOut]:
    """Same per-investigation rollup GET /api/investigations/{id} already
    computes — re-surfaced here under the "who was consulted" framing this
    issue asks for, not recomputed differently."""
    totals: dict[str, dict] = defaultdict(lambda: {"steps": 0, "total_duration_ms": 0})
    for s in investigation.steps:
        totals[s.agent_name]["steps"] += 1
        totals[s.agent_name]["total_duration_ms"] += s.duration_ms
    return [
        InvestigationAgentSummaryOut(agent_name=name, steps=v["steps"], total_duration_ms=v["total_duration_ms"])
        for name, v in totals.items()
    ]


def _confidence_breakdown(investigation: Investigation) -> ConfidenceOut:
    """[EXPLAIN] issue #90. Only agents that actually produced a
    confidence value are included — never a fabricated 0% for the
    classifier/planner/memory steps, which genuinely don't have one."""
    by_agent = [
        ConfidenceBreakdownOut(agent_name=s.agent_name, confidence=s.confidence)
        for s in sorted(investigation.steps, key=lambda s: s.step_number)
        if s.confidence is not None
    ]
    return ConfidenceOut(overall=investigation.confidence_score, by_agent=by_agent)


def _evidence(investigation: Investigation) -> EvidenceOut:
    """[EXPLAIN] issue #91. `policy_references` is exactly the
    `type == "kb_article"` subset of `evidence_refs` — not a separately
    tracked list, so the two can never drift apart."""
    all_prose: list[str] = []
    all_refs: list[dict] = []
    for s in investigation.steps:
        all_prose.extend(s.evidence)
        all_refs.extend(s.evidence_refs)
    policy_refs = [r for r in all_refs if r.get("type") == "kb_article"]
    return EvidenceOut(evidence=all_prose, evidence_refs=all_refs, policy_references=policy_refs)


def _alternatives(investigation: Investigation) -> list[dict]:
    """[EXPLAIN] issue #89. Alternatives are only ever recorded on the
    planner's own step (see orchestrator.py's _record() call site) — there
    is at most one such step per investigation."""
    for s in investigation.steps:
        if s.agent_name == "planner" and s.alternatives_considered:
            return s.alternatives_considered
    return []


def _chosen_action(investigation: Investigation) -> str | None:
    """[EXPLAIN] issue #96: which of resolve/clarify/escalate was actually
    chosen — needed so the frontend can show it visually distinct from
    (never mixed into) the rejected alternatives above.

    Not a stored column of its own — orchestrator.py's planner _record()
    call always builds the step's `action` label deterministically as
    exactly one of "Decided to resolve via the X specialist",
    "Decided to clarify", or "Decided to escalate" (see
    orchestrator.py's `plan_action` local). Parsing that fixed,
    code-controlled string (never raw LLM prose) is simpler and safer
    than adding a second column that would just duplicate what's already
    unambiguously encoded in the planner step's action text.
    """
    for s in investigation.steps:
        if s.agent_name != "planner":
            continue
        if s.action.startswith("Decided to resolve"):
            return "resolve"
        if "clarify" in s.action:
            return "clarify"
        if "escalate" in s.action:
            return "escalate"
    return None


def _decision_rationale(investigation: Investigation, db: Session) -> str:
    """Deterministic composition, no new LLM call (issue #92's explicit
    design choice). Resolved: root_cause + resolution, both already
    computed by the specialist/orchestrator. Escalated: falls back to the
    persisted HandoffPacket's root_cause_hypothesis + recommended_action
    (see orchestrator.py::_create_ticket / build_handoff_packet), since a
    resolved-style root_cause may never have been produced on that path.
    """
    if investigation.status == "escalated":
        ticket = db.get(Ticket, investigation.ticket_id)
        if ticket and ticket.handoff_packet_json:
            packet = json.loads(ticket.handoff_packet_json)
            parts = [p for p in (packet.get("root_cause_hypothesis"), packet.get("recommended_action")) if p]
            if parts:
                return " ".join(parts)
        return investigation.root_cause or "Escalated to a human agent — see the handoff packet for full context."

    parts = [p for p in (investigation.root_cause, investigation.resolution) if p]
    return " ".join(parts) if parts else "Resolved — see the reasoning timeline for the full explanation."


@router.get("/{investigation_id}/explanation", response_model=ExplanationOut)
def get_explanation(investigation_id: int, db: Session = Depends(get_db)) -> ExplanationOut:
    """The Explainable AI Panel's single source of data."""
    investigation = _get_investigation(investigation_id, db)
    evidence = _evidence(investigation)
    return ExplanationOut(
        investigation_id=investigation.id,
        status=investigation.status,
        confidence=_confidence_breakdown(investigation),
        evidence=evidence.evidence,
        evidence_refs=evidence.evidence_refs,
        policy_references=evidence.policy_references,
        chosen_action=_chosen_action(investigation),
        alternatives_considered=_alternatives(investigation),
        agents_consulted=_agents_consulted(investigation),
        decision_rationale=_decision_rationale(investigation, db),
    )


@router.get("/{investigation_id}/evidence", response_model=EvidenceOut)
def get_investigation_evidence(investigation_id: int, db: Session = Depends(get_db)) -> EvidenceOut:
    """Lightweight — for a widget that only needs evidence/policy refs
    without pulling the whole explanation."""
    return _evidence(_get_investigation(investigation_id, db))


@router.get("/{investigation_id}/confidence", response_model=ConfidenceOut)
def get_investigation_confidence(investigation_id: int, db: Session = Depends(get_db)) -> ConfidenceOut:
    """Lightweight — for a widget that only needs the confidence gauge."""
    return _confidence_breakdown(_get_investigation(investigation_id, db))
