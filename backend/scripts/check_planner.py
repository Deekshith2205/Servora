"""One-off sanity check for issue #4 ("[P0] Implement Planner/Orchestrator
routing logic") — acceptance criteria: a calm-but-unresolvable request
escalates even without negative sentiment.

Run from backend/ with your .env filled in (uses the real DB via
app.db.database — make sure the app has run at least once to seed it):
    ./.venv/Scripts/python.exe -m scripts.check_planner
"""
from app.agents.classifier import ClassificationResult
from app.agents.planner import plan
from app.db.database import SessionLocal
from app.db.seed import seed_if_empty

SCENARIOS = [
    (
        "Calm tone, but a serious/repeated problem — should still escalate",
        ClassificationResult(
            category="account",
            sentiment="neutral",
            urgency=9,
            reasoning="Customer calmly describes a repeated critical failure.",
        ),
    ),
    (
        "Frustrated tone, but a simple fixable request — can still resolve",
        ClassificationResult(
            category="order",
            sentiment="negative",
            urgency=3,
            reasoning="Customer is annoyed about a routine shipping delay.",
        ),
    ),
]


def main() -> None:
    seed_if_empty()
    db = SessionLocal()
    try:
        for label, classification in SCENARIOS:
            decision = plan(classification, customer_id=1, db=db)
            print(f"scenario:  {label}")
            print(f"action:    {decision.action}")
            print(f"target:    {decision.target_agent}")
            print(f"reasoning: {decision.reasoning}")
            print("-" * 60)
    finally:
        db.close()


if __name__ == "__main__":
    main()
