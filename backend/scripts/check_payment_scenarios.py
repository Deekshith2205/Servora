"""One-off sanity check for the Connected Commerce demo-polish pass's new
payment-only tools (get_customer_payments / check_payment_anomaly /
issue_payment_refund) — verifies the Billing specialist actually reaches
and resolves a payment that has NO linked order, bypassing the Planner
so a high-open-ticket-count account risk score can't route this straight
to escalation instead (same reason check_billing.py calls resolve_billing
directly rather than going through handle_message()).

Run from backend/ with your .env filled in (uses the real dev DB):
    ./.venv/Scripts/python.exe -m scripts.check_payment_scenarios
"""
from app.agents.specialists import resolve_billing
from app.db.database import SessionLocal
from app.db.models import Customer, Payment
from app.db.seed import seed_if_empty


def main() -> None:
    seed_if_empty()
    db = SessionLocal()
    try:
        alice = db.query(Customer).filter(Customer.email == "alice@example.com").first()

        before = [
            (p.id, p.description, p.status, p.order_id, p.duplicate_of)
            for p in db.query(Payment).filter(Payment.customer_id == alice.id).all()
        ]
        print("payments before:")
        for row in before:
            print(" ", row)

        result = resolve_billing(
            db, alice.id,
            "I think I was charged twice for my Noise Cancelling Earbuds but I only see one order in my account.",
        )

        print(f"\nused_tools: {result.used_tools}")
        print(f"confidence: {result.confidence}")
        print(f"root_cause: {result.root_cause}")
        print(f"reply:      {result.reply}")
        print(f"evidence:   {result.evidence}")
        print(f"evidence_refs: {result.evidence_refs}")

        after = [
            (p.id, p.description, p.status, p.order_id, p.duplicate_of)
            for p in db.query(Payment).filter(Payment.customer_id == alice.id).all()
        ]
        print("\npayments after:")
        for row in after:
            print(" ", row)
    finally:
        db.close()


if __name__ == "__main__":
    main()
