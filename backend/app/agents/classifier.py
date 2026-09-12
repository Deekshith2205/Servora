"""Classifier Agent. Implements issue #3 ("[P0] Implement Classifier Agent").

Contract kept as-is (do not change without updating orchestrator.py and the
frontend trace view):

    classify(message: str) -> ClassificationResult

ClassificationResult:
    category:  "billing" | "technical" | "order" | "account" | "general"
    sentiment: "positive" | "neutral" | "negative"
    urgency:   int 1-10
    reasoning: a short human-readable explanation for the score (not just
               the label) — judges/teammates should be able to see *why*.
"""
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.llm import LLMError, call_llm

VALID_CATEGORIES = ("billing", "technical", "order", "account", "general")
VALID_SENTIMENTS = ("positive", "neutral", "negative")

SYSTEM_PROMPT = """You are the Classifier Agent in an autonomous customer \
support pipeline. Given a customer's message, determine:

- category: exactly one of billing, technical, order, account, general
- sentiment: exactly one of positive, neutral, negative — the customer's \
emotional tone, not the situation's severity
- urgency: an integer 1-10, judged from what's actually at stake for the \
customer (money at risk, time-criticality, a repeated or escalating \
failure) — not just how strongly worded the message is. A calm message \
about an unresolvable problem can still be high urgency.
- reasoning: one or two sentences explaining WHY you chose these values. \
This is shown to a human reviewer, so state the specific signal in the \
message that drove the score — do not just restate the labels \
("category is billing because it's about billing" is not acceptable).
"""


@dataclass
class ClassificationResult:
    category: str
    sentiment: str
    urgency: int
    reasoning: str
    confidence: float


class _ClassificationSchema(BaseModel):
    category: str = Field(description="One of: billing, technical, order, account, general")
    sentiment: str = Field(description="One of: positive, neutral, negative")
    urgency: int = Field(ge=1, le=10, description="1 = no rush, 10 = critical")
    reasoning: str = Field(description="Why these values — cite the specific signal in the message")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in this classification, from 0.0 to 1.0")


def classify(message: str) -> ClassificationResult:
    try:
        result = call_llm(
            system_prompt=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": message}],
            response_schema=_ClassificationSchema,
            max_tokens=500,
        )

        category = result.category if result.category in VALID_CATEGORIES else "general"
        sentiment = result.sentiment if result.sentiment in VALID_SENTIMENTS else "neutral"
        urgency = max(1, min(10, result.urgency))
        confidence = max(0.0, min(1.0, result.confidence))
        reasoning = result.reasoning
    except LLMError:
        msg = message.lower()
        if any(term in msg for term in ("billing", "payment", "refund", "charge", "charged", "invoice")):
            category = "billing"
        elif any(term in msg for term in ("order", "shipping", "tracking", "delivery", "shipped", "arrived")):
            category = "order"
        elif any(term in msg for term in ("booking", "room", "reservation", "hotel")):
            category = "booking"
        else:
            category = "general"
            
        sentiment = "neutral"
        urgency = 5
        confidence = 0.0
        reasoning = "LLM classification unavailable; deterministic fallback classification used."

    return ClassificationResult(
        category=category,
        sentiment=sentiment,
        urgency=urgency,
        reasoning=reasoning,
        confidence=confidence,
    )
