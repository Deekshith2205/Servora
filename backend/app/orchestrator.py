"""Wires classify -> plan -> specialist -> verify into one call.

This already runs end-to-end today (against the stubs), so the frontend has
something real to hit from day one. As each agent issue lands, this file
should need NO structural changes — only the stub bodies get replaced.
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.agents.classifier import classify
from app.agents.planner import plan
from app.agents.specialists import SPECIALISTS
from app.agents.verification import verify


@dataclass
class TraceStep:
    agent: str
    output: str


@dataclass
class ChatResult:
    reply: str
    status: str  # resolved | escalated
    trace: list[TraceStep] = field(default_factory=list)


def handle_message(db: Session, customer_id: int, message: str) -> ChatResult:
    trace: list[TraceStep] = []

    classification = classify(message)
    trace.append(TraceStep("classifier", classification.reasoning))

    decision = plan(classification)
    trace.append(TraceStep("planner", decision.reasoning))

    if decision.action == "escalate":
        trace.append(TraceStep("escalation", "Routed straight to a human agent."))
        return ChatResult(reply="A human agent will follow up shortly.", status="escalated", trace=trace)

    specialist_fn = SPECIALISTS.get(decision.target_agent, SPECIALISTS["technical"])
    response = specialist_fn(db, customer_id, message)
    trace.append(TraceStep(f"{decision.target_agent}_specialist", response.reply))

    verification = verify(response)
    trace.append(TraceStep("verification", verification.reasoning))

    if not verification.approved:
        trace.append(TraceStep("escalation", "Verification failed — escalating to a human agent."))
        return ChatResult(reply="A human agent will follow up shortly.", status="escalated", trace=trace)

    return ChatResult(reply=response.reply, status="resolved", trace=trace)
