"""One-off sanity check for issue [P0] "Wire a real LLM provider into the
agent stubs" — acceptance criteria: this script gets a real completion,
both in plain-text mode and structured-output mode.

Run from backend/ with your .env filled in:
    ./.venv/Scripts/python.exe -m scripts.check_llm
"""
from pydantic import BaseModel

from app.llm import call_llm


class Sentiment(BaseModel):
    sentiment: str  # positive | neutral | negative
    reasoning: str


def main() -> None:
    print("-- plain text call --")
    text = call_llm(
        system_prompt="You are a terse assistant.",
        messages=[{"role": "user", "content": "Say hello in five words or fewer."}],
        max_tokens=100,
    )
    print(text)

    print("\n-- structured output call --")
    result = call_llm(
        system_prompt="Classify the sentiment of the customer's message.",
        messages=[{"role": "user", "content": "This is the third time my order has been delayed!"}],
        response_schema=Sentiment,
        max_tokens=300,
    )
    print(result)


if __name__ == "__main__":
    main()
