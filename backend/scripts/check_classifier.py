"""One-off sanity check for issue #3 ("[P0] Implement Classifier Agent") —
acceptance criteria: "I was charged twice" classifies as category=billing,
sentiment=negative, urgency high, with a real reasoning string.

Run from backend/ with your .env filled in:
    ./.venv/Scripts/python.exe -m scripts.check_classifier
"""
from app.agents.classifier import classify

EXAMPLES = [
    "I was charged twice for my smart watch order.",
    "Hey, just wondering when my headphones will ship?",
    "This is the third time this month your app has crashed on checkout!!",
    "Thanks so much, the refund came through perfectly.",
]


def main() -> None:
    for message in EXAMPLES:
        result = classify(message)
        print(f"message:   {message}")
        print(f"category:  {result.category}")
        print(f"sentiment: {result.sentiment}")
        print(f"urgency:   {result.urgency}")
        print(f"reasoning: {result.reasoning}")
        print("-" * 60)


if __name__ == "__main__":
    main()
