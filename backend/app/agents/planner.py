"""Planner Agent — STUB. Tracked by issue: "Implement Planner/Orchestrator routing".

Given a ClassificationResult + customer context, decides ONE of:
    "resolve"   -> route to the matching specialist agent
    "clarify"   -> ask the customer a follow-up question
    "escalate"  -> skip straight to the Escalation Agent

This is the piece that makes routing more than an if/else on category —
it should weigh urgency, sentiment, and whether this customer has an
unresolved history on the same topic (see memory.py) before deciding.
"""
from dataclasses import dataclass

from app.agents.classifier import ClassificationResult


@dataclass
class PlanDecision:
    action: str  # resolve | clarify | escalate
    target_agent: str  # billing | technical | order | account | none
    reasoning: str


def plan(classification: ClassificationResult) -> PlanDecision:
    # TODO(issue: planner-orchestrator): replace with real decision logic.
    return PlanDecision(
        action="resolve",
        target_agent=classification.category if classification.category != "general" else "technical",
        reasoning="STUB: planner not implemented yet — defaulting to resolve.",
    )
