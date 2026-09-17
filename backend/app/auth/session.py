"""Real login sessions — issuing and resolving the bearer token
`POST /api/auth/login`/`/register` hand back. See `AuthSession`'s own
docstring in app/db/models.py for why this is a DB table, not a JWT."""
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.db.models import AuthSession

SESSION_TTL = timedelta(days=7)


def create_session(db: Session, actor_type: str, actor_id: int) -> AuthSession:
    session = AuthSession(
        token=secrets.token_urlsafe(32),
        actor_type=actor_type,
        actor_id=actor_id,
        expires_at=datetime.utcnow() + SESSION_TTL,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def resolve_session(db: Session, token: str) -> AuthSession | None:
    """Returns None for a missing, unknown, or expired token — never
    raises. An expired session is deliberately left in the table rather
    than deleted here (a read shouldn't also be a write); it's inert
    either way since it never resolves to a real actor again."""
    session = db.query(AuthSession).filter(AuthSession.token == token).first()
    if session is None or session.expires_at < datetime.utcnow():
        return None
    return session


def invalidate_session(db: Session, token: str) -> bool:
    session = db.query(AuthSession).filter(AuthSession.token == token).first()
    if session is None:
        return False
    db.delete(session)
    db.commit()
    return True
