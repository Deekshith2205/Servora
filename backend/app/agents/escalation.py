"""Escalation Agent — STUB. Tracked by issue: "Implement Escalation Agent + confidence threshold".

Produces the structured handoff packet a human agent actually needs —
not a raw transcript dump. See docs/ARCHITECTURE.md for the required
sections (Situation / Attempted Fixes / Root-Cause Hypothesis /
Recommended Action / Urgency).
"""
from dataclasses import dataclass


@dataclass
class HandoffPacket:
    situation: str
    attempted_fixes: list[str]
    root_cause_hypothesis: str
    recommended_action: str
    urgency: int


def build_handoff_packet(message: str) -> HandoffPacket:
    # TODO(issue: escalation-agent): populate from real conversation + trace state.
    return HandoffPacket(
        situation=message,
        attempted_fixes=[],
        root_cause_hypothesis="STUB: not implemented yet.",
        recommended_action="STUB: not implemented yet.",
        urgency=1,
    )
