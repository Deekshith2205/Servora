"""One-off sanity check for issue #17 ("[P3] Learning Agent: draft KB
updates from resolved escalations") — acceptance criteria: resolving an
escalated ticket shows a KB suggestion; a reusable fix gets should_add=True,
a one-off exception gets should_add=False.

Run from backend/ with your .env filled in:
    ./.venv/Scripts/python.exe -m scripts.check_learning
"""
from app.agents.learning import draft_kb_article

SCENARIOS = [
    (
        "Reusable fix — should suggest a KB article",
        dict(
            category="billing",
            customer_message="I was charged twice for my order.",
            resolution_notes="Turned out this customer was still on the legacy billing plan, which "
            "double-submits the charge. Migrated them to the current plan, then issued the refund.",
        ),
    ),
    (
        "One-off exception — should NOT suggest a KB article",
        dict(
            category="billing",
            customer_message="Can you waive my late fee just this once?",
            resolution_notes="Granted a one-time goodwill waiver as a courtesy for a long-time customer.",
        ),
    ),
]


def main() -> None:
    for label, kwargs in SCENARIOS:
        draft = draft_kb_article(**kwargs)
        print(f"scenario:   {label}")
        print(f"should_add: {draft.should_add}")
        print(f"title:      {draft.title}")
        print(f"body:       {draft.body}")
        print(f"tags:       {draft.tags}")
        print("-" * 60)


if __name__ == "__main__":
    main()
