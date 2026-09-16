"""[FEATURE] "AI Investigation Board & Autonomous Reasoning Timeline".

Read-only API over the Investigation/InvestigationStep rows
orchestrator.py::_persist_investigation() writes alongside the existing
Ticket.trace_json snapshot — see that function's docstring and
app/db/models.py's Investigation docstring for why this is a separate,
normalized table rather than re-parsing trace_json harder.
"""
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.schemas import (
    AgentPerformanceOut,
    GraphEdgeOut,
    GraphNodeOut,
    InvestigationAgentSummaryOut,
    InvestigationGraphOut,
    InvestigationListItemOut,
    InvestigationMetricsOut,
    InvestigationOut,
    InvestigationStepOut,
)
from app.auth.dependency import CurrentActor, get_current_actor, require_any_permission, require_permission
from app.auth.investigation_visibility import can_view_investigation
from app.db.database import get_db
from app.db.models import Investigation, InvestigationStep

router = APIRouter(prefix="/api/investigations", tags=["investigations"])


def _to_investigation_out(investigation: Investigation) -> InvestigationOut:
    steps = sorted(investigation.steps, key=lambda s: s.step_number)

    agent_totals: dict[str, dict] = defaultdict(lambda: {"steps": 0, "total_duration_ms": 0})
    all_evidence: list[str] = []
    for s in steps:
        agent_totals[s.agent_name]["steps"] += 1
        agent_totals[s.agent_name]["total_duration_ms"] += s.duration_ms
        all_evidence.extend(s.evidence)

    return InvestigationOut(
        id=investigation.id,
        ticket_id=investigation.ticket_id,
        customer_id=investigation.customer_id,
        started_at=investigation.started_at.isoformat(),
        completed_at=investigation.completed_at.isoformat() if investigation.completed_at else None,
        confidence=investigation.confidence_score,
        root_cause=investigation.root_cause,
        resolution=investigation.resolution,
        status=investigation.status,
        channel_metadata=investigation.channel_metadata,
        channel=investigation.channel_key,
        timeline=[
            InvestigationStepOut(
                step_number=s.step_number,
                timestamp=s.timestamp.isoformat(),
                started_at=s.started_at.isoformat() if s.started_at else None,
                agent_name=s.agent_name,
                action=s.action,
                status=s.status,
                reasoning=s.reasoning_text,
                evidence=s.evidence,
                evidence_refs=s.evidence_refs,
                used_tools=s.used_tools,
                alternatives_considered=s.alternatives_considered,
                critic_review=s.critic_review,
                duration_ms=s.duration_ms,
                confidence=s.confidence,
            )
            for s in steps
        ],
        agents=[
            InvestigationAgentSummaryOut(agent_name=name, steps=vals["steps"], total_duration_ms=vals["total_duration_ms"])
            for name, vals in agent_totals.items()
        ],
        evidence=all_evidence,
        graph=_build_graph(steps),
    )


def _build_graph(steps: list[InvestigationStep]) -> InvestigationGraphOut:
    """[SWARM] issues #80/#78. Edges now come from each step's explicit
    `depends_on` (issue #78) rather than an assumption that step order
    alone implies dependency — today the two always agree (the pipeline
    never fans out), but the graph builder itself no longer needs to know
    that; it just renders whatever `depends_on` says, so a future
    fan-out/fan-in change only needs orchestrator.py to set different
    values there."""
    nodes = [
        GraphNodeOut(step_number=s.step_number, agent_name=s.agent_name, status=s.status,
                     confidence=s.confidence, duration_ms=s.duration_ms)
        for s in steps
    ]
    by_step_number = {s.step_number: s for s in steps}
    edges = [
        GraphEdgeOut(from_step=dep, to_step=s.step_number)
        for s in steps
        for dep in s.depends_on
        if dep in by_step_number
    ]
    return InvestigationGraphOut(nodes=nodes, edges=edges)


@router.get("", response_model=list[InvestigationListItemOut])
def list_investigations(
    limit: int = 50,
    db: Session = Depends(get_db),
    _actor: CurrentActor = Depends(require_permission("view_investigation_board")),
) -> list[Investigation]:
    """Recent investigations, newest first — backs the Investigation
    Board's browse list. [RBAC] issue #187: staff-only, no per-customer
    data scoping — matches how this page already works today."""
    investigations = (
        db.query(Investigation).order_by(Investigation.started_at.desc()).limit(limit).all()
    )
    return [
        InvestigationListItemOut(
            id=inv.id,
            ticket_id=inv.ticket_id,
            customer_id=inv.customer_id,
            status=inv.status,
            root_cause=inv.root_cause,
            confidence=inv.confidence_score,
            started_at=inv.started_at.isoformat(),
            channel=inv.channel_key,
            channel_metadata=inv.channel_metadata,
        )
        for inv in investigations
    ]


@router.get("/metrics/agents", response_model=InvestigationMetricsOut)
def agent_performance_metrics(
    db: Session = Depends(get_db),
    _actor: CurrentActor = Depends(require_any_permission("view_investigation_board", "view_analytics")),
) -> InvestigationMetricsOut:
    """Cross-investigation aggregate per agent — a real SQL GROUP BY over
    every InvestigationStep ever recorded, not a per-investigation view.
    This is the data behind the Investigation Board's "Agent Performance
    Metrics" section. [RBAC] issue #194: reachable via EITHER a Support
    Agent's `view_investigation_board` OR a Manager's `view_analytics` —
    a Manager who never got the former must still reach this one
    specific metrics endpoint, since it's explicitly named in their own
    spec."""
    rows = (
        db.query(
            InvestigationStep.agent_name,
            func.count(InvestigationStep.id),
            func.avg(InvestigationStep.duration_ms),
            func.avg(InvestigationStep.confidence),
        )
        .group_by(InvestigationStep.agent_name)
        .all()
    )
    return InvestigationMetricsOut(
        agents=[
            AgentPerformanceOut(
                agent_name=name,
                total_steps=count,
                avg_duration_ms=round(avg_duration or 0.0, 1),
                avg_confidence=round(avg_confidence, 2) if avg_confidence is not None else None,
            )
            for name, count, avg_duration, avg_confidence in rows
        ]
    )


@router.get("/by-ticket/{ticket_id}", response_model=InvestigationOut)
def get_investigation_by_ticket(
    ticket_id: int, db: Session = Depends(get_db), actor: CurrentActor = Depends(get_current_actor)
) -> InvestigationOut:
    """Convenience lookup for callers that only have a ticket_id in hand
    (e.g. ChatResult.ticket_id from /api/chat, or a row from
    GET /api/escalations) — Investigation<->Ticket is 1:1.

    [RBAC] issue #217: gated via `can_view_investigation()` — the SAME
    helper `get_investigation()` below calls, so a Customer viewing
    their own investigation and staff viewing any investigation share
    one real rule, not two independently-drifting checks."""
    investigation = db.query(Investigation).filter_by(ticket_id=ticket_id).first()
    if investigation is None:
        raise HTTPException(status_code=404, detail=f"No investigation recorded for ticket {ticket_id}")
    if not can_view_investigation(actor, investigation):
        raise HTTPException(status_code=403, detail="You do not have permission to perform this action.")
    return _to_investigation_out(investigation)


@router.get("/{investigation_id}", response_model=InvestigationOut)
def get_investigation(
    investigation_id: int, db: Session = Depends(get_db), actor: CurrentActor = Depends(get_current_actor)
) -> InvestigationOut:
    """[RBAC] issue #217: same `can_view_investigation()` helper as
    `get_investigation_by_ticket()` above."""
    investigation = db.get(Investigation, investigation_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail=f"Investigation {investigation_id} not found")
    if not can_view_investigation(actor, investigation):
        raise HTTPException(status_code=403, detail="You do not have permission to perform this action.")
    return _to_investigation_out(investigation)
