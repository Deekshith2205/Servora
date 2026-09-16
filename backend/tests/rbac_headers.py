"""[RBAC] shared test helper — the real identity headers every gated
endpoint's tests need to send, matching how `app.auth.dependency.
get_current_actor()` actually resolves an actor. Not a fixture (so it
works identically for tests using the shared session-wide test DB and
tests building their own isolated in-memory engine) — plain functions.
"""
from app.db.models import Customer, User


def staff_headers(db, role: str = "administrator") -> dict:
    """Looks up (or, for an isolated test engine, creates) a real
    staff `User` row with the given role and returns the identity
    headers for it. `X-Servora-Role` only needs to be a valid STAFF
    role string to route `get_current_actor()` into the staff lookup
    branch — the actual role used is the resolved `User` row's own
    `role` column, never the header's claim (see that function's own
    docstring for why)."""
    user = db.query(User).filter(User.role == role).first()
    if user is None:
        user = User(name=f"Test {role}", email=f"test-{role}@example.com", role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
    return {"X-Servora-Role": role, "X-Servora-User-Id": str(user.id)}


def customer_headers(customer_id: int) -> dict:
    return {"X-Servora-Role": "customer", "X-Servora-Customer-Id": str(customer_id)}
