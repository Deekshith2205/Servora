"""One-off sanity check for issue #6 ("[P1] Implement Billing specialist
agent") — acceptance criteria: "I was charged twice for my smart watch"
actually flips the seeded order to refunded and cites the refund policy.

Run from backend/ with your .env filled in (uses the real dev DB — run the
app once first so it's seeded, per db/seed.py):
    ./.venv/Scripts/python.exe -m scripts.check_billing
"""
from app.agents.specialists import resolve_billing
from app.db.database import SessionLocal
from app.db.models import Order
from app.db.seed import seed_if_empty


def main() -> None:
    seed_if_empty()
    db = SessionLocal()
    try:
        # Bob (customer_id=2 in the seed data) has the "Smart Watch" order.
        customer_id = 2
        before = [
            (o.id, o.status) for o in db.query(Order).filter(Order.customer_id == customer_id).all()
        ]
        print(f"orders before: {before}")

        result = resolve_billing(db, customer_id, "I was charged twice for my smart watch")

        print(f"used_tools: {result.used_tools}")
        print(f"confidence: {result.confidence}")
        print(f"reply:      {result.reply}")

        after = [
            (o.id, o.status) for o in db.query(Order).filter(Order.customer_id == customer_id).all()
        ]
        print(f"orders after:  {after}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
