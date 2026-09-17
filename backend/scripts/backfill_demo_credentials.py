"""One-off backfill for real login/registration — the 5 seeded demo
accounts (2 customers, 3 staff) predate `Credential`/`AuthSession`.
`app/db/seed.py::seed_if_empty()` only runs against a genuinely EMPTY
database, so it can never retroactively give these existing rows a
real password on a database that's already populated — which is
exactly this app's real deployed state (a persistent Neon Postgres
database, not a local file that gets deleted and reseeded). This
script does that one-time backfill directly, idempotently (skips any
account that already has a Credential row, so it's safe to re-run).

Run from backend/ with your .env filled in:
    ./.venv/Scripts/python.exe -m scripts.backfill_demo_credentials
"""
from app.auth.password import hash_password
from app.auth.roles import CUSTOMER
from app.db.database import SessionLocal
from app.db.models import Credential, Customer, User

_DEMO_PASSWORD = "Demo1234!"
_DEMO_CUSTOMER_EMAILS = ["alice@example.com", "bob@example.com"]
_DEMO_STAFF_EMAILS = ["jordan.lee@servora.example", "priya.shah@servora.example", "sam.okafor@servora.example"]


def _has_credential(db, actor_type: str, actor_id: int) -> bool:
    return db.query(Credential).filter(Credential.actor_type == actor_type, Credential.actor_id == actor_id).first() is not None


def main() -> None:
    db = SessionLocal()
    created = 0
    try:
        for email in _DEMO_CUSTOMER_EMAILS:
            customer = db.query(Customer).filter(Customer.email == email).first()
            if customer is None:
                print(f"  skip (no such customer): {email}")
                continue
            if _has_credential(db, CUSTOMER, customer.id):
                print(f"  already has a credential: {email}")
                continue
            db.add(Credential(actor_type=CUSTOMER, actor_id=customer.id, password_hash=hash_password(_DEMO_PASSWORD)))
            created += 1
            print(f"  backfilled: {email}")

        for email in _DEMO_STAFF_EMAILS:
            user = db.query(User).filter(User.email == email).first()
            if user is None:
                print(f"  skip (no such user): {email}")
                continue
            if _has_credential(db, "staff", user.id):
                print(f"  already has a credential: {email}")
                continue
            db.add(Credential(actor_type="staff", actor_id=user.id, password_hash=hash_password(_DEMO_PASSWORD)))
            created += 1
            print(f"  backfilled: {email}")

        db.commit()
    finally:
        db.close()

    print(f"\nDone — {created} credential row(s) created. Demo password: {_DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
