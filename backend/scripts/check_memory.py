"""One-off sanity check for issue #11 ("[P1] Implement customer memory
write/merge") — acceptance criteria: ask about the same issue twice across
two separate handle_message calls for the same customer_id, and the
second response should reference what was learned in the first.

Run from backend/ with your .env filled in:
    ./.venv/Scripts/python.exe -m scripts.check_memory
"""
from app.db.database import SessionLocal
from app.db.models import CustomerMemory
from app.db.seed import seed_if_empty
from app.orchestrator import handle_message


def main() -> None:
    seed_if_empty()
    db = SessionLocal()
    try:
        customer_id = 2  # Bob — has a billing ticket in the seed data

        # Clear any memory from a previous run of this script.
        existing = db.get(CustomerMemory, customer_id)
        if existing is not None:
            db.delete(existing)
            db.commit()

        print("--- Turn 1 ---")
        result1 = handle_message(db, customer_id, "I was charged twice for my smart watch, please just waive the fee this once")
        print(f"reply:  {result1.reply}")
        print(f"status: {result1.status}")
        for step in result1.trace:
            print(f"  [{step.agent}] {step.output}")

        record = db.get(CustomerMemory, customer_id)
        print(f"\nmemory after turn 1: {record.facts_json if record else '(nothing stored)'}")

        print("\n--- Turn 2 (same customer, related follow-up) ---")
        result2 = handle_message(db, customer_id, "Following up on my last message — any update?")
        print(f"reply:  {result2.reply}")
        print(f"status: {result2.status}")
        for step in result2.trace:
            print(f"  [{step.agent}] {step.output}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
