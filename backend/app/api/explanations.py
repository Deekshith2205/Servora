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
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import (
    ConfidenceBreakdownOut,
    ConfidenceOut,
    EvidenceConfidenceBreakdownOut,
    EvidenceDetailOut,
    EvidenceOut,
    EvidenceRefOut,
    ExplanationOut,
    InvestigationAgentSummaryOut,
    ToolExecutionOut,
)
from app.db.database import get_db
from app.db.models import Investigation, InvestigationStep, Ticket

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
    """The Explainability Panel's single source of data."""
    investigation = _get_investigation(investigation_id, db)
    evidence = _evidence(investigation)
    return ExplanationOut(
        investigation_id=investigation.id,
        status=investigation.status,
        channel=investigation.channel_key,
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


# --------------------------------------------------------------------- #
# [Explainability #123]: evidence drill-down — the Investigation Board's
# new Explainability Drawer's single data source.
# --------------------------------------------------------------------- #

# [Explainability #122]: source-reliability-by-type. A structured DB
# record lookup (order/customer/ticket) is a direct, literal fact; a KB
# article match is a policy/text match chosen by relevance, inherently a
# notch less certain than a database row — the same "tool-only grounding"
# philosophy _estimate_confidence() in specialists.py already applies to
# whole specialist responses, applied here per evidence item instead.
_SOURCE_RELIABILITY_BY_TYPE = {
    "order": 0.97,
    "customer": 0.97,
    "ticket": 0.95,
    "kb_article": 0.88,
    # A real Shopify lookup is the actual system of record for that order
    # — not a local copy that could have drifted — so it's rated even
    # higher than this app's own mocked/seeded Order table, not lower.
    "shopify_order": 0.99,
    "shopify_customer": 0.99,
}


def _find_step(investigation: Investigation, step_number: int) -> InvestigationStep | None:
    return next((s for s in investigation.steps if s.step_number == step_number), None)


def _parse_evidence_id(evidence_id: str) -> tuple[int, int]:
    """"{step_number}:{index}" -> (step_number, index). Raises ValueError
    on anything malformed, which the endpoint turns into a 400 — evidence
    refs aren't individually-addressable DB rows today (see
    EvidenceDetailOut's docstring), so this composite string key is the
    whole addressing scheme; keep the parsing in one place."""
    step_number_str, _, index_str = evidence_id.partition(":")
    return int(step_number_str), int(index_str)


def _evidence_reasoning(step: InvestigationStep) -> str:
    """Real `reasoning_text` when the step recorded one. When it didn't
    (some steps — e.g. escalation — don't always produce a reasoning
    narrative distinct from their `action` label), a deterministic
    fallback composed from what WAS recorded, never a fabricated
    explanation: same "generate structured explanation from stored data"
    approach this endpoint's spec asked for, and the same no-new-LLM-call
    convention as _decision_rationale() above."""
    if step.reasoning_text:
        return step.reasoning_text
    if step.used_tools:
        tools = ", ".join(step.used_tools)
        return f"{step.action} — gathered by calling {tools}."
    return step.action


def _evidence_tools(step: InvestigationStep) -> list[ToolExecutionOut]:
    """See ToolExecutionOut's docstring for why duration/records-returned
    are step-level values attributed to every tool the step used, not
    independently tracked per tool call. `used_tools` can legitimately
    repeat a name (e.g. search_kb called with several different queries
    within one step, as `specialists.py`'s retry-with-a-different-query
    logic does) — de-duplicated here, since listing the same tool 2-3
    times with identical step-level stats would just be visual noise,
    not real information (and would collide as a React list key on the
    frontend)."""
    records_returned = len(step.evidence_refs) or len(step.evidence)
    seen = dict.fromkeys(step.used_tools)  # de-dupe, preserve first-seen order
    return [
        ToolExecutionOut(tool_name=name, duration_ms=step.duration_ms, records_returned=records_returned)
        for name in seen
    ]


def _evidence_confidence_breakdown(
    investigation: Investigation, step: InvestigationStep, evidence_ref: dict
) -> EvidenceConfidenceBreakdownOut:
    """Three deterministic sub-scores, each derived from a real, existing
    signal — no random numbers, no new LLM call:

    - Evidence Quality: the step's own confidence (0.6 as a neutral
      floor for steps that never produce one, e.g. classifier/planner),
      nudged up slightly for each additional structured evidence ref the
      step produced — more corroborating evidence is genuinely better
      evidence, capped so it can never read as a fabricated 100%.
    - Data Freshness: every fact behind an evidence ref was queried live
      from the DB at the moment the investigation ran (this project's
      tool-only-grounding rule) — freshness is therefore a real function
      of how long ago THAT was, not a constant. Decays gently, floored
      at 0.5 rather than reading as "stale" just because an
      investigation is old.
    - Source Reliability: see _SOURCE_RELIABILITY_BY_TYPE above.
    """
    base_confidence = step.confidence if step.confidence is not None else 0.6
    evidence_quality = min(0.99, base_confidence + 0.03 * len(step.evidence_refs))

    age_hours = max(0.0, (datetime.utcnow() - investigation.started_at).total_seconds() / 3600)
    data_freshness = max(0.5, 1.0 - min(age_hours, 500) / 1000)

    source_reliability = _SOURCE_RELIABILITY_BY_TYPE.get(evidence_ref.get("type"), 0.85)

    return EvidenceConfidenceBreakdownOut(
        evidence_quality=round(evidence_quality, 2),
        data_freshness=round(data_freshness, 2),
        source_reliability=round(source_reliability, 2),
    )


def _evidence_impact(investigation: Investigation, step: InvestigationStep) -> str:
    """One sentence on how this evidence item affected the investigation
    — composed from fields already on the investigation/step, same
    deterministic-composition convention as _decision_rationale()."""
    if step.status == "failed":
        return "This step's evidence gathering failed and did not contribute a usable finding."
    if investigation.status == "escalated":
        return "Contributed to the decision to escalate this case to a human agent."
    if investigation.root_cause:
        return f"Supports the investigation's root cause: {investigation.root_cause}"
    if investigation.resolution:
        return f"Supported the resolution: {investigation.resolution}"
    return "Part of the evidence gathered during this investigation."


@router.get("/{investigation_id}/evidence/{evidence_id}", response_model=EvidenceDetailOut)
def get_evidence_detail(investigation_id: int, evidence_id: str, db: Session = Depends(get_db)) -> EvidenceDetailOut:
    """The Explainability Drawer's single source of data for one evidence
    item. See EvidenceDetailOut's docstring for the addressing scheme and
    why the source record itself isn't re-embedded here."""
    investigation = _get_investigation(investigation_id, db)

    try:
        step_number, index = _parse_evidence_id(evidence_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Malformed evidence id {evidence_id!r} — expected '<step_number>:<index>'")

    step = _find_step(investigation, step_number)
    if step is None or index < 0 or index >= len(step.evidence_refs):
        raise HTTPException(status_code=404, detail=f"Evidence item {evidence_id!r} not found on investigation {investigation_id}")

    evidence_ref = step.evidence_refs[index]

    return EvidenceDetailOut(
        investigation_id=investigation.id,
        evidence_id=evidence_id,
        step_number=step.step_number,
        title=evidence_ref["label"],
        agent_name=step.agent_name,
        timestamp=step.timestamp.isoformat(),
        confidence=step.confidence,
        evidence_ref=EvidenceRefOut(**evidence_ref),
        reasoning=_evidence_reasoning(step),
        tools=_evidence_tools(step),
        confidence_breakdown=_evidence_confidence_breakdown(investigation, step, evidence_ref),
        impact=_evidence_impact(investigation, step),
    )
