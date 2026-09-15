"""[Omnichannel] Phase 3 — Channel Message Flow (issues #142-#145).

The architectural core of the whole Omnichannel epic: one normalization
function per non-Live-Chat channel, all funneling into
`route_channel_message()`, which is the ONLY caller of
`orchestrator.handle_message()` for those channels — the exact same
function `POST /api/chat` (app/api/chat.py) already calls for Live Chat.
No second investigation pipeline is created anywhere here; this module's
entire job is turning one channel's raw inbound shape into the inputs
that function already accepts.

Real transport is out of reach in this environment (WhatsApp/Instagram/
Messenger need Meta Business verification + app review; a real inbound
email pipeline needs a receiving domain/webhook) — every `normalize_*`
function below works against a realistic, documented RAW PAYLOAD SHAPE
for that channel's real webhook format, but nothing in this module
receives one over the network yet. A future issue wires a real
webhook endpoint to `route_channel_message()`; this is the normalization
logic that endpoint would call, already correct and already tested
against representative fixtures.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.db.models import Customer, Investigation
from app.orchestrator import ChatResult, handle_message


@dataclass
class NormalizedMessage:
    """The common shape every channel's raw payload boils down to —
    `orchestrator.handle_message()`'s actual inputs, plus enough contact
    info to resolve (or create) the right `Customer` row. Exactly one of
    `contact_email`/`contact_phone`/`contact_external_id` is expected to
    be set per channel (see `_resolve_or_create_customer()`)."""

    channel: str
    message: str
    channel_metadata: dict = field(default_factory=dict)
    contact_email: str | None = None
    contact_phone: str | None = None
    contact_external_id: str | None = None
    contact_name: str | None = None


def normalize_whatsapp(payload: dict) -> NormalizedMessage:
    """Raw shape: a single WhatsApp Cloud API inbound-message webhook
    entry, e.g.::

        {
            "from": "15555550101",
            "id": "wamid.HBgLMTU1NTU1NTU1MDEVAgARGBI5QTQ0RUE3RjZBOEQ4RjZFAA==",
            "text": {"body": "Where is my order?"},
        }

    `from` is the customer's phone number (no `+`, per WhatsApp's own
    convention) — the only contact info this channel natively provides,
    so customer resolution happens by phone (see
    `_resolve_or_create_customer()`)."""
    phone = payload["from"]
    return NormalizedMessage(
        channel="whatsapp",
        message=payload["text"]["body"],
        channel_metadata={"external_conversation_id": payload.get("id"), "external_contact": phone},
        contact_phone=phone,
    )


def normalize_instagram(payload: dict) -> NormalizedMessage:
    """Raw shape: a single Instagram Messaging webhook entry (same family
    as Messenger's, just under a distinct `entry.messaging` path in
    Meta's real webhook envelope)::

        {
            "sender": {"id": "1784235678"},
            "message": {"mid": "aWdfZAG1faXRlbToxOgE...", "text": "..."},
        }

    Instagram provides no phone/email at all — only an opaque,
    Instagram-Scoped sender ID. Customer resolution therefore happens by
    that external ID (see `_resolve_or_create_customer()`), an honest
    scope limit: the `Customer` model has no native "Instagram handle"
    field, so a first-time sender becomes a new `Customer` with a
    synthesized, channel-prefixed placeholder email."""
    sender_id = payload["sender"]["id"]
    return NormalizedMessage(
        channel="instagram",
        message=payload["message"]["text"],
        channel_metadata={"external_conversation_id": payload["message"].get("mid"), "external_contact": sender_id},
        contact_external_id=sender_id,
    )


def normalize_messenger(payload: dict) -> NormalizedMessage:
    """Raw shape: a single Messenger Platform webhook entry — structurally
    identical to Instagram's (both are Meta Messaging Platform products),
    same "opaque sender ID only" limitation."""
    sender_id = payload["sender"]["id"]
    return NormalizedMessage(
        channel="messenger",
        message=payload["message"]["text"],
        channel_metadata={"external_conversation_id": payload["message"].get("mid"), "external_contact": sender_id},
        contact_external_id=sender_id,
    )


def normalize_email(payload: dict) -> NormalizedMessage:
    """Raw shape: a generic inbound-email-parse webhook (the same shape
    most providers — Mailgun, SendGrid, Postmark — normalize a real
    inbound email into)::

        {
            "from": "alice@example.com",
            "subject": "Order question",
            "body": "Where is my order?",
            "message_id": "<CAF+abc123@mail.example.com>",
        }

    Email is the one non-Live-Chat channel where `Customer.email` (the
    model's existing, real unique key) is a direct, natural match — no
    synthesized placeholder needed."""
    return NormalizedMessage(
        channel="email",
        message=payload["body"],
        channel_metadata={"external_conversation_id": payload.get("message_id"), "subject": payload.get("subject")},
        contact_email=payload["from"],
    )


_NORMALIZERS = {
    "whatsapp": normalize_whatsapp,
    "instagram": normalize_instagram,
    "messenger": normalize_messenger,
    "email": normalize_email,
}


def _resolve_or_create_customer(db: Session, normalized: NormalizedMessage) -> Customer:
    """Resolves the SAME real `Customer` row across repeated messages
    from the same real contact — the mechanism issue #144 (conversation
    synchronization) actually depends on: since `load_profile()`
    (app/agents/memory.py, issue #11) already merges facts across every
    prior interaction for a `customer_id`, getting this resolution right
    is what makes cross-turn/cross-channel context "just work" via
    existing memory, with no second continuity mechanism needed.

    Priority: email > phone > external_id — email is the model's own
    real unique key, so it's preferred whenever a channel provides one.
    """
    if normalized.contact_email:
        customer = db.query(Customer).filter(Customer.email == normalized.contact_email).first()
        if customer:
            return customer
        customer = Customer(
            name=normalized.contact_name or normalized.contact_email.split("@")[0],
            email=normalized.contact_email,
            phone=normalized.contact_phone or "",
        )
    elif normalized.contact_phone:
        customer = db.query(Customer).filter(Customer.phone == normalized.contact_phone).first()
        if customer:
            return customer
        customer = Customer(
            name=normalized.contact_name or f"{normalized.channel.title()} Customer {normalized.contact_phone}",
            email=f"{normalized.channel}+{normalized.contact_phone.lstrip('+')}@channel.local",
            phone=normalized.contact_phone,
        )
    elif normalized.contact_external_id:
        placeholder_email = f"{normalized.channel}+{normalized.contact_external_id}@channel.local"
        customer = db.query(Customer).filter(Customer.email == placeholder_email).first()
        if customer:
            return customer
        customer = Customer(
            name=normalized.contact_name or f"{normalized.channel.title()} Customer {normalized.contact_external_id}",
            email=placeholder_email,
            phone="",
        )
    else:
        raise ValueError("NormalizedMessage must carry a contact_email, contact_phone, or contact_external_id.")

    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def route_channel_message(
    db: Session, channel_key: str, raw_payload: dict, stream_key: str | None = None
) -> ChatResult:
    """[Omnichannel] issue #142 — the ONE entry point every non-Live-Chat
    channel funnels through. Normalizes the raw payload, resolves/creates
    the real `Customer`, then calls the EXACT SAME
    `orchestrator.handle_message()` every existing caller (POST
    /api/chat included) already calls — never a second pipeline, never a
    shortcut around Classifier/Planner/Specialists/Critic/Verification/
    Escalation.
    """
    normalizer = _NORMALIZERS.get(channel_key)
    if normalizer is None:
        raise ValueError(f"No normalizer registered for channel '{channel_key}'.")

    normalized = normalizer(raw_payload)
    customer = _resolve_or_create_customer(db, normalized)

    return handle_message(
        db,
        customer.id,
        normalized.message,
        stream_key=stream_key,
        channel=channel_key,
        channel_metadata=normalized.channel_metadata,
    )


def find_recent_conversation_on_channel(
    db: Session, customer_id: int, channel_key: str, external_conversation_id: str | None
) -> Investigation | None:
    """[Omnichannel] issue #144 — finds the most recent Investigation on
    this exact external thread for this customer/channel, if one exists.
    Read-only: does NOT change `route_channel_message()`'s own per-call
    behavior (every inbound message still produces its own Investigation
    — see `orchestrator.handle_message()`'s docstring). Intended for a
    future Inbox (#136+) to group messages into one conversation view;
    this issue's own deliverable is the correct lookup, not a merge
    mechanism (there isn't one — see this module's own docstring on why
    a second pipeline/state machine is explicitly out of scope).

    Scans the customer's most recent investigations on this channel in
    Python rather than a SQL JSON query — simple and correct at this
    scale (a handful of recent conversations per customer), not a
    performance-sensitive path worth a JSON-column index for."""
    if not external_conversation_id:
        return None
    candidates = (
        db.query(Investigation)
        .filter(Investigation.customer_id == customer_id, Investigation.channel_key == channel_key)
        .order_by(Investigation.started_at.desc())
        .limit(20)
        .all()
    )
    for inv in candidates:
        meta = inv.channel_metadata
        if meta and meta.get("external_conversation_id") == external_conversation_id:
            return inv
    return None


_MARKDOWN_BOLD_ITALIC = re.compile(r"\*\*(.+?)\*\*|\*(.+?)\*|__(.+?)__|_(.+?)_")
_MARKDOWN_INLINE_CODE = re.compile(r"`([^`]+)`")
_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_MARKDOWN_BULLET = re.compile(r"^[ \t]*[-*][ \t]+", re.MULTILINE)


def _strip_markdown(text: str) -> str:
    text = _MARKDOWN_LINK.sub(r"\1 (\2)", text)
    text = _MARKDOWN_INLINE_CODE.sub(r"\1", text)
    text = _MARKDOWN_BOLD_ITALIC.sub(lambda m: next(g for g in m.groups() if g is not None), text)
    text = _MARKDOWN_BULLET.sub("• ", text)
    return text


def format_reply_for_channel(reply: str, channel_key: str) -> str:
    """[Omnichannel] issue #143 — formats an already-decided reply for
    the channel it's headed to. Never changes WHAT was decided (that's
    every agent upstream's job) — only HOW the same text is presented.

    - `live_chat`: passed through byte-for-byte unchanged — this is the
      one channel already proven correct in production, and this
      function must never regress it.
    - `whatsapp`/`instagram`/`messenger`: markdown stripped (no rich
      text support on these platforms) via a plain regex substitution,
      not a full markdown parser dependency — good enough for the
      simple bold/italic/code/link/bullet patterns this codebase's own
      replies actually produce.
    - `email`: passed through unchanged — email natively renders
      markdown-ish plain text fine, and fabricating a subject
      line/signature that wasn't part of the agent's actual reply would
      misrepresent what was decided. (The real subject line lives in
      `channel_metadata["subject"]`, already captured by
      `normalize_email()` — a future email-sending integration reads it
      from there, not from the reply body.)

    NOT yet wired into the real `handle_message()`/`route_channel_message()`
    reply path — that's a separate, later issue ([Omnichannel] #151,
    "Response formatting by channel"). This function is deliberately
    proven correct in isolation first.
    """
    if channel_key in ("whatsapp", "instagram", "messenger"):
        return _strip_markdown(reply)
    return reply
