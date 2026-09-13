"""Critic Agent. Implements issue #109 ("Implement Critic Agent —
independent review of root cause, evidence, and resolution").

`verification.py::verify()` is explicitly documented as an approximation:
two deterministic checks (a confidence threshold, a narrow completed-
action phrase match), not a semantic review — "a real semantic/second-
LLM-judge pass would catch more, at the cost of another network call per
verification — a reasonable future hardening, not done here." This agent
is that hardening: a genuine second LLM opinion on whatever a specialist
(or, after issue #88's reconciliation, the combined finding of several
specialists) concluded.

Deliberately advisory, not a gate: this agent reviews and records an
opinion — it does not change whether Verification approves a reply or
whether the conversation escalates. See orchestrator.py's wiring
(issue #110) for why that's an explicit, documented non-goal of this
batch rather than a silent limitation.
"""
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.agents.specialists import SpecialistResponse
from app.llm import LLMError, call_llm

SYSTEM_PROMPT = """You are the Critic Agent in an autonomous customer \
support pipeline. A specialist has already investigated a customer's \
issue and produced a root cause, a resolution, and the evidence it \
gathered along the way. Your job is to independently review that work — \
not to redo the investigation, but to sanity-check it the way a second, \
skeptical reviewer would before it reaches a customer.

Review the root cause, the resolution, and the evidence together:
- Does the evidence actually support the stated root cause, or is there a \
gap the specialist glossed over?
- Is the resolution a reasonable response to that root cause, or does it \
overreach (e.g. claiming more than the evidence shows) or underreach \
(e.g. missing an obvious implication of the evidence)?

Decide:
- agrees: true if the root cause and resolution are well-supported by the \
evidence; false if you found a real gap, contradiction, or overreach.
- confidence: YOUR OWN confidence in this review, 0.0-1.0 — not a copy of \
the specialist's confidence, and not automatically high just because the \
specialist sounded sure.
- alternative_hypothesis: only when you disagree (or see a plausible \
competing explanation worth flagging) — a specific, different explanation \
for what's actually going on. Leave this empty when you agree.
- reasoning: cite the SPECIFIC evidence or claim that drove your verdict — \
never a generic "this looks correct" or "this seems reasonable" with no \
reference to what was actually reviewed."""


@dataclass
class CriticReview:
    agrees: bool
    confidence: float  # 0-1, the critic's OWN confidence in its review
    alternative_hypothesis: str | None
    reasoning: str


class _CriticSchema(BaseModel):
    agrees: bool = Field(description="True if the root cause/resolution are well-supported by the evidence")
    confidence: float = Field(ge=0.0, le=1.0, description="The critic's own confidence in this review, 0.0-1.0")
    alternative_hypothesis: str | None = Field(
        default=None,
        description="A specific competing explanation, only when disagreeing or flagging a real alternative. Empty otherwise.",
    )
    reasoning: str = Field(description="Cite the specific evidence/claim reviewed — not a generic verdict")


def _context_for(specialist_response: SpecialistResponse, message: str) -> str:
    lines = [f"Customer's original message: {message}"]
    if specialist_response.root_cause:
        lines.append(f"Specialist's stated root cause: {specialist_response.root_cause}")
    if specialist_response.resolution:
        lines.append(f"Specialist's stated resolution: {specialist_response.resolution}")
    if not specialist_response.root_cause and not specialist_response.resolution:
        # A specialist that never populated either field (e.g. account/
        # technical read-only replies) — review the reply text itself
        # rather than two empty fields.
        lines.append(f"Specialist's reply: {specialist_response.reply}")
    if specialist_response.evidence:
        lines.append("Evidence the specialist gathered:\n" + "\n".join(f"- {e}" for e in specialist_response.evidence))
    else:
        lines.append("The specialist gathered no tool-derived evidence at all.")
    # Deliberately NOT included: specialist_response.confidence — see this
    # module's docstring for why the critic must not just defer to it.
    return "\n\n".join(lines)


def critique(specialist_response: SpecialistResponse, message: str) -> CriticReview:
    try:
        result = call_llm(
            system_prompt=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _context_for(specialist_response, message)}],
            response_schema=_CriticSchema,
            max_tokens=500,
        )
        confidence = max(0.0, min(1.0, result.confidence))
        # Defensive against a contradictory response (agrees=True but the
        # model filled in alternative_hypothesis anyway): when the critic
        # agrees, there is no alternative to surface, full stop — never
        # pass through stray text just because the field happened to be
        # non-empty.
        alternative_hypothesis = result.alternative_hypothesis if not result.agrees else None
        return CriticReview(
            agrees=bool(result.agrees),
            confidence=confidence,
            alternative_hypothesis=alternative_hypothesis,
            reasoning=result.reasoning,
        )
    except LLMError as exc:
        # Advisory agent, same fail-safe spirit as classifier.py's
        # deterministic fallback: a critic that can't run must never break
        # the customer-facing response. Degrades to a low-confidence
        # "agrees" (never a fabricated disagreement) so a caller can still
        # tell this wasn't a real review.
        return CriticReview(
            agrees=True, confidence=0.0, alternative_hypothesis=None,
            reasoning=f"Critic review unavailable — the review call failed: {exc}",
        )
