"""Verification Agent. Implements issue #10 ("[P1] Implement Verification
Agent").

Sits between a specialist's proposed resolution and it actually being shown
to the customer / executed. This is what makes "reasoning" visible instead
of trusting the first agent's output blindly — see docs/ARCHITECTURE.md.

Two deliberately cheap, deterministic checks (no second LLM call — keeps
this network-free to test and instant in production):

1. Confidence threshold — see specialists.py::_estimate_confidence() for
   how confidence is derived (0.9 action taken, 0.6 grounded-only, 0.2 no
   tools used). Below the threshold, the reply isn't grounded enough to
   show the customer unchecked.
2. Completed-action consistency — catches a specialist's final text
   claiming it *completed* an action (e.g. "I've issued a refund") when
   the corresponding action tool never actually ran. Deliberately narrow:
   matches only clear completion phrasing, not any mention of the concept
   ("this doesn't qualify for a refund" must NOT be flagged — see the
   false-positive-avoidance test in tests/test_verification.py). This is
   an approximation, not a semantic check; a real NLI/second-LLM-judge
   pass would catch more, at the cost of another network call per
   verification — a reasonable future hardening, not done here.
"""
from dataclasses import dataclass

from app.agents.specialists import SpecialistResponse

# Below this, a reply isn't grounded enough to show the customer unchecked.
_CONFIDENCE_THRESHOLD = 0.5

# Phrases that assert an action was *completed*, mapped to the tool that
# must appear in used_tools to back up that claim. Extend this map if a
# new action tool is added (currently only issue_refund exists).
_COMPLETED_ACTION_PHRASES: dict[str, str] = {
    "issued a refund": "issue_refund",
    "issued your refund": "issue_refund",
    "i've issued": "issue_refund",
    "i have issued": "issue_refund",
    "refund has been issued": "issue_refund",
    "refund has been processed": "issue_refund",
    "processed your refund": "issue_refund",
    "refund is on its way": "issue_refund",
}


@dataclass
class VerificationResult:
    approved: bool
    reasoning: str


def verify(response: SpecialistResponse) -> VerificationResult:
    if response.confidence < _CONFIDENCE_THRESHOLD:
        return VerificationResult(
            approved=False,
            reasoning=(
                f"Confidence {response.confidence:.1f} is below the {_CONFIDENCE_THRESHOLD} "
                f"threshold (used_tools={response.used_tools or 'none'}) — not grounded enough "
                "to show the customer without a human check."
            ),
        )

    reply_lower = response.reply.lower()
    for phrase, required_tool in _COMPLETED_ACTION_PHRASES.items():
        if phrase in reply_lower and required_tool not in response.used_tools:
            return VerificationResult(
                approved=False,
                reasoning=(
                    f"Reply claims a completed action ({phrase!r}) but {required_tool!r} was "
                    f"never actually called (used_tools={response.used_tools}) — likely an "
                    "ungrounded claim."
                ),
            )

    return VerificationResult(
        approved=True,
        reasoning=(
            f"Confidence {response.confidence:.1f} meets the {_CONFIDENCE_THRESHOLD} threshold "
            f"and no unsupported completed-action claims were detected (used_tools={response.used_tools})."
        ),
    )
