"""Classifier Agent — STUB. Tracked by issue: "Implement Classifier Agent".

Contract it must fulfil (don't change the shape without updating callers in
orchestrator.py and the frontend trace view):

    classify(message: str) -> ClassificationResult

ClassificationResult must include, at minimum:
    category:  "billing" | "technical" | "order" | "account" | "general"
    sentiment: "positive" | "neutral" | "negative"
    urgency:   int 1-10
    reasoning: a short human-readable explanation for the score (not just
               the label) — judges/teammates should be able to see *why*.

Real implementation should call the LLM with a structured-output schema
(Pydantic) rather than parsing free text.
"""
from dataclasses import dataclass


@dataclass
class ClassificationResult:
    category: str
    sentiment: str
    urgency: int
    reasoning: str


def classify(message: str) -> ClassificationResult:
    # TODO(issue: classifier-agent): replace with a real LLM call.
    return ClassificationResult(
        category="general",
        sentiment="neutral",
        urgency=1,
        reasoning="STUB: classifier not implemented yet — see README/issues.",
    )
