"""Verification Agent — STUB. Tracked by issue: "Implement Verification Agent".

Sits between a specialist's proposed resolution and it actually being shown
to the customer / executed. This is what makes "reasoning" visible instead
of trusting the first agent's output blindly — see docs/ARCHITECTURE.md.

Must return whether the resolution is safe to send, and if not, why (which
routes back to the Planner for a retry, or to Escalation).
"""
from dataclasses import dataclass

from app.agents.specialists import SpecialistResponse


@dataclass
class VerificationResult:
    approved: bool
    reasoning: str


def verify(response: SpecialistResponse) -> VerificationResult:
    # TODO(issue: verification-agent): real confidence/consistency checks.
    return VerificationResult(approved=True, reasoning="STUB: verification not implemented yet — auto-approving.")
