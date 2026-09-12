"""Learning Agent. Implements issue #17 ("[P3] Learning Agent: draft KB
updates from resolved escalations").

Closes the loop from "handled once" to "the system gets smarter": when a
staff member resolves an escalated ticket, this drafts a candidate KB
article from what actually happened — never auto-published, always
surfaced for a human to approve first (see api/tickets.py's resolve
endpoint and api/kb.py's approve endpoint).

Deliberately conservative: most resolutions are one-off and account-
specific (a goodwill exception, a typo in an address) and should NOT
become a KB article. The agent is explicitly instructed to say so
(`should_add=False`) rather than manufacture a generic-sounding article
out of a non-reusable case.
"""
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.llm import call_llm


@dataclass
class DraftKBArticle:
    should_add: bool
    title: str
    body: str
    tags: list[str]


class _DraftSchema(BaseModel):
    should_add: bool = Field(
        description="Whether this resolution is worth adding as a durable KB article — false for "
        "a one-off, account-specific action with no general lesson (e.g. a goodwill exception "
        "granted to one customer). True only if a similar future case would benefit."
    )
    title: str = Field(description="Short, searchable title. Empty string if should_add is false.")
    body: str = Field(
        description="The article: what the issue was and how it was resolved, written generally "
        "enough to help with a similar future case — not this specific customer's details. "
        "Empty string if should_add is false."
    )
    tags: list[str] = Field(
        description="1-3 short lowercase topic tags (e.g. 'billing', 'refund'). Empty list if "
        "should_add is false."
    )


_SYSTEM_PROMPT = """You review a resolved customer support escalation and decide whether it is \
worth adding to the knowledge base as a reusable article for future tickets.

Only propose adding one if the resolution would genuinely help with a SIMILAR FUTURE case — not \
a one-off, account-specific action. For example: "waived this specific customer's late fee as a \
goodwill exception" is NOT reusable and should get should_add=false. "Customers on the legacy \
billing plan need to be migrated manually before a refund can be issued" IS reusable.

If it is not reusable, set should_add to false and leave title/body/tags empty — do not force a \
generic-sounding article out of a case that doesn't warrant one. If it is reusable, write a \
concise, generally-applicable article a future agent or teammate could act on directly."""


def draft_kb_article(
    category: str,
    customer_message: str,
    resolution_notes: str,
    root_cause_hypothesis: str | None = None,
    recommended_action: str | None = None,
) -> DraftKBArticle:
    context_lines = [
        f"Category: {category}",
        f"Customer's original message: {customer_message}",
        f"How a human agent resolved it: {resolution_notes or '(no notes provided)'}",
    ]
    if root_cause_hypothesis:
        context_lines.append(f"AI's root-cause hypothesis at escalation time: {root_cause_hypothesis}")
    if recommended_action:
        context_lines.append(f"AI's recommended action at escalation time: {recommended_action}")

    result = call_llm(
        system_prompt=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": "\n".join(context_lines)}],
        response_schema=_DraftSchema,
        max_tokens=500,
    )

    return DraftKBArticle(
        should_add=result.should_add,
        title=result.title,
        body=result.body,
        tags=result.tags,
    )
