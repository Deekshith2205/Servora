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
    """[SWARM] issue #80. See GraphEdgeOut's docstring: today's pipeline
    never fans out, so "step N depends on step N-1" is a correct (not
    just convenient) edge set for every branch this app can currently
    produce — a direct-Planner escalation is just a shorter chain, not a
    different shape."""
    nodes = [
        GraphNodeOut(step_number=s.step_number, agent_name=s.agent_name, status=s.status,
                     confidence=s.confidence, duration_ms=s.duration_ms)
        for s in steps
    ]
    edges = [
        GraphEdgeOut(from_step=steps[i].step_number, to_step=steps[i + 1].step_number)
        for i in range(len(steps) - 1)
    ]
    return InvestigationGraphOut(nodes=nodes, edges=edges)


@router.get("", response_model=list[InvestigationListItemOut])
def list_investigations(limit: int = 50, db: Session = Depends(get_db)) -> list[Investigation]:
    """Recent investigations, newest first — backs the Investigation
    Board's browse list."""
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
        )
        for inv in investigations
    ]


@router.get("/metrics/agents", response_model=InvestigationMetricsOut)
def agent_performance_metrics(db: Session = Depends(get_db)) -> InvestigationMetricsOut:
    """Cross-investigation aggregate per agent — a real SQL GROUP BY over
    every InvestigationStep ever recorded, not a per-investigation view.
    This is the data behind the Investigation Board's "Agent Performance
    Metrics" section."""
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
def get_investigation_by_ticket(ticket_id: int, db: Session = Depends(get_db)) -> InvestigationOut:
    """Convenience lookup for callers that only have a ticket_id in hand
    (e.g. ChatResult.ticket_id from /api/chat, or a row from
    GET /api/escalations) — Investigation<->Ticket is 1:1."""
    investigation = db.query(Investigation).filter_by(ticket_id=ticket_id).first()
    if investigation is None:
        raise HTTPException(status_code=404, detail=f"No investigation recorded for ticket {ticket_id}")
    return _to_investigation_out(investigation)


@router.get("/{investigation_id}", response_model=InvestigationOut)
def get_investigation(investigation_id: int, db: Session = Depends(get_db)) -> InvestigationOut:
    investigation = db.get(Investigation, investigation_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail=f"Investigation {investigation_id} not found")
    return _to_investigation_out(investigation)
