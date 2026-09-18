"""SQLAlchemy engine/session setup.

SQLite for the hackathon — swap DATABASE_URL in .env if you move to a real
database later; nothing else in the app needs to change.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# [SWARM] issue #88: `check_same_thread: False` already let a connection be
# used from a different thread than the one that created it, but until #88
# nothing in this app ever ran two DB-writing specialists concurrently.
# Now that `orchestrator.py`'s parallel fan-out does exactly that (each
# thread gets its OWN `SessionLocal()`, never a shared one — see
# `_run_specialist_isolated()`), two independent connections against the
# same SQLite file CAN legitimately contend for its write lock at the same
# moment. SQLite's own default busy-timeout is 0 (fail immediately as
# `database is locked` rather than wait) — a `timeout` here makes a
# connection wait a few seconds for the lock instead, which is the
# difference between "a rare demo flake" and "a real, reproducible bug."
connect_args = {"check_same_thread": False, "timeout": 15} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def run_migrations(engine_obj):
    """Minimal schema migration for the ticket.resolved_at addition.
    Runs idempotently on startup.
    """
    if not engine_obj.url.drivername.startswith("sqlite"):
        return
        
    with engine_obj.begin() as conn:
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='tickets'")).fetchone()
        if not result:
            return
            
        columns = conn.execute(text("PRAGMA table_info('tickets')")).fetchall()
        has_resolved_at = any(col[1] == 'resolved_at' for col in columns)
        
        if not has_resolved_at:
            conn.execute(text("ALTER TABLE tickets ADD COLUMN resolved_at DATETIME"))



class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yields a session, always closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
