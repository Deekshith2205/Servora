"""Escalation Agent. Implements issue #12 ("[P2] Implement Escalation
Agent + confidence threshold").

Builds the structured handoff packet a human agent actually needs — not
a raw transcript dump. Called from orchestrator.py at both points a
conversation escalates (a direct Planner "escalate" decision, or a
failed Verification) — see docs/ARCHITECTURE.md for the full graph.

Scope note: the resolve-vs-escalate *decision* is already made upstream
(by the Planner, or by Verification's confidence check) — this agent
does not re-decide that. Its job is turning whatever context led to that
decision into something a human can act on immediately. It cites
Verification's `CONFIDENCE_THRESHOLD` (made public there for this reason)
rather than duplicating the number.
"""
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.agents.verification import CONFIDENCE_THRESHOLD
from app.llm import call_llm


@dataclass
class HandoffPacket:
    situation: str
    attempted_fixes: list[str]
    root_cause_hypothesis: str
    recommended_action: str
    urgency: int


class _HandoffSchema(BaseModel):
    situation: str = Field(
        description="One or two plain-language sentences summarizing what the customer needs — "
        "written for a human agent who has never seen this conversation."
    )
    root_cause_hypothesis: str = Field(
        description="Best guess at WHY this needs a human — cite what was actually tried and "
        "what's missing, uncertain, or outside the AI's authority. Not generic."
    )
    recommended_action: str = Field(description="One concrete next step the human agent should take.")


_HANDOFF_SYSTEM_PROMPT = """You write escalation handoff notes for a human support agent picking \
up a case an AI could not resolve on its own. Be concise, concrete, and specific — cite exactly \
what was already tried and why it wasn't enough. Never generic advice like "look into this \
further." The human agent has not seen this conversation."""


def build_handoff_packet(
    message: str,
    attempted_fixes: list[str],
    urgency: int,
    confidence: float | None = None,
) -> HandoffPacket:
    """`attempted_fixes` and `urgency` are supplied by the caller
    (orchestrator.py already has the trace and the classifier's urgency
    score) — this function's job is the LLM-driven summary, not deciding
    what was tried or how urgent it is.
    """
    context_lines = [f"Customer's message: {message}"]
    if attempted_fixes:
        context_lines.append(
            "What happened before escalation, in order:\n" + "\n".join(f"- {f}" for f in attempted_fixes)
        )
    else:
        context_lines.append("This was escalated immediately, before any resolution was attempted.")
    if confidence is not None:
        context_lines.append(
            f"The AI's confidence in its attempted resolution was {confidence:.1f} "
            f"(automatic approval requires at least {CONFIDENCE_THRESHOLD})."
        )

    result = call_llm(
        system_prompt=_HANDOFF_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": "\n\n".join(context_lines)}],
        response_schema=_HandoffSchema,
        max_tokens=500,
    )

    return HandoffPacket(
        situation=result.situation,
        attempted_fixes=attempted_fixes,
        root_cause_hypothesis=result.root_cause_hypothesis,
        recommended_action=result.recommended_action,
        urgency=urgency,
    )
