"""Customer memory. Implements issue #11 ("[P1] Implement customer memory
write/merge").

Storage: a small `customer_memory` table (one row per customer — see
`CustomerMemory` in `app/db/models.py`), holding a JSON list of short
"facts" learned about the customer over time (preferences, exceptions
granted, notable recurring issues). Deliberately a flat list of strings,
not a rich schema — the only operation that matters is set-union merge.

CONTRACT CHANGE from the original stubs: both functions now take `db:
Session` (they need real DB access) — `load_profile(customer_id)` became
`load_profile(customer_id, db)`, same for `merge_profile`. Callers
updated: `planner.py` (already had `db` in scope from issue #4) and
`specialists.py::_run_specialist` (already had `db` too). No public API
route touches these directly, so the blast radius is just those two
call sites.

Rule to keep (see docs/ARCHITECTURE.md — "memory as merge, not
overwrite"): a new turn's extracted facts are UNION-merged into whatever
is already stored. An empty or failed extraction is a no-op — it must
never erase a previously known fact.
"""
from __future__ import annotations

import json

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import CustomerMemory
from app.llm import call_llm

# Keep the profile small enough that it's cheap to inject into every
# specialist/planner prompt — oldest facts are dropped once this is exceeded.
_MAX_FACTS_PER_CUSTOMER = 20

_EXTRACTION_SYSTEM_PROMPT = """You extract durable facts worth remembering \
about a customer from one support interaction. Only extract something that \
would still matter in a future, unrelated conversation — a stated \
preference, a one-time exception granted, a pattern of repeated issues. \
Do NOT extract transient details (a specific order number, today's date, \
this ticket's exact wording) unless they reflect an ongoing pattern. If \
nothing durable stood out, return an empty list — do not force it."""


class _ExtractedFacts(BaseModel):
    facts: list[str] = Field(
        description="0-3 short, durable facts worth remembering about this customer. "
        "Empty list if nothing durable stood out."
    )


def load_profile(customer_id: int, db: Session) -> dict:
    """Returns {"facts": [...]} if anything is known, else {}."""
    record = db.get(CustomerMemory, customer_id)
    if record is None:
        return {}
    facts = json.loads(record.facts_json)
    return {"facts": facts} if facts else {}


def extract_facts(message: str, reply: str) -> list[str]:
    """Summarize one turn into 0-3 durable facts via structured LLM output.

    Lets LLMError propagate (see app/llm.py) — the caller (orchestrator)
    decides whether a failed extraction should skip memory writing for
    this turn rather than break the customer-facing response.
    """
    result = call_llm(
        system_prompt=_EXTRACTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Customer message: {message}\n\nAgent's reply: {reply}"}],
        response_schema=_ExtractedFacts,
        max_tokens=300,
    )
    return result.facts


def merge_profile(customer_id: int, new_facts: list[str], db: Session) -> None:
    """Set-union merge new_facts into the stored profile.

    A no-op when new_facts is empty — never erases what's already known.
    Order-preserving, deduplicated, capped at _MAX_FACTS_PER_CUSTOMER
    (keeping the most recent).
    """
    if not new_facts:
        return

    record = db.get(CustomerMemory, customer_id)
    if record is None:
        record = CustomerMemory(customer_id=customer_id, facts_json="[]")
        db.add(record)
        existing: list[str] = []
    else:
        existing = json.loads(record.facts_json)

    merged = list(dict.fromkeys(existing + new_facts))  # union, de-duped, order-preserving
    if len(merged) > _MAX_FACTS_PER_CUSTOMER:
        merged = merged[-_MAX_FACTS_PER_CUSTOMER:]

    record.facts_json = json.dumps(merged)
    db.commit()
