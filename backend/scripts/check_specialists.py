"""One-off sanity check for issues #7, #8, #9 (Technical/Order/Account
specialist agents) against the real seeded demo data.

Run from backend/ with your .env filled in:
    ./.venv/Scripts/python.exe -m scripts.check_specialists
"""
from app.agents.specialists import resolve_account, resolve_order, resolve_technical
from app.db.database import SessionLocal
from app.db.seed import seed_if_empty


def _run(label: str, fn, customer_id: int, message: str) -> None:
    db = SessionLocal()
    try:
        result = fn(db, customer_id, message)
        print(f"[{label}] message:    {message}")
        print(f"[{label}] used_tools: {result.used_tools}")
        print(f"[{label}] confidence: {result.confidence}")
        print(f"[{label}] reply:      {result.reply}")
        print("-" * 60)
    finally:
        db.close()


def main() -> None:
    seed_if_empty()
    # Alice (customer_id=1) has a "Wireless Headphones" order and is VIP.
    _run("technical", resolve_technical, 1, "The app keeps crashing every time I try to check out.")
    _run("technical-no-match", resolve_technical, 1, "My smart fridge won't connect to the app.")
    _run("order", resolve_order, 1, "It's been days, where is my order?")
    _run("account", resolve_account, 1, "What's the email on file for my account?")
    _run("account-out-of-scope", resolve_account, 1, "Can you reset my password?")


if __name__ == "__main__":
    main()
