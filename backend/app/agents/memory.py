"""Customer memory — STUB. Tracked by issue: "Implement customer memory write/merge".

Rule to keep when implementing (see docs/ARCHITECTURE.md — "memory as merge,
not overwrite"): new turns should be UNION-merged into whatever the customer
profile already holds. An empty/failed extraction must be a no-op, never an
overwrite — a bad LLM turn should never erase a real fact you already knew
about this customer.
"""


def load_profile(customer_id: int) -> dict:
    # TODO(issue: customer-memory): load from a real per-customer store.
    return {}


def merge_profile(customer_id: int, new_facts: dict) -> None:
    # TODO(issue: customer-memory): set-union merge into persistent storage.
    pass
