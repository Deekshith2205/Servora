"""[Omnichannel] issue #143 (channel-specific formatting) + #151 (wiring
it into the real reply path).

Split out of `channel_adapters.py` into its own module specifically to
avoid a circular import: `channel_adapters.py` imports `handle_message`/
`ChatResult` from `orchestrator.py` (issue #142), and issue #151 needs
`orchestrator.py` to import `format_reply_for_channel` in the other
direction — the two modules can't import each other. This file has no
dependency on either, so both can import from it safely.
`channel_adapters.py` re-exports this function for backward
compatibility with anything that already imports it from there.
"""
from __future__ import annotations

import re

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
    """Formats an already-decided reply for the channel it's headed to.
    Never changes WHAT was decided (that's every agent upstream's job)
    — only HOW the same text is presented.

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

    [Omnichannel] issue #151: called from `orchestrator.py::handle_message()`
    at every point it builds a `ChatResult.reply` — both the resolved-
    specialist-reply path and the escalation "a human agent will follow
    up shortly" path — via that function's own `_finalize_reply()` local
    helper, so the actual call to this function happens in exactly one
    place in `orchestrator.py`, not reimplemented per branch. Every
    non-Live-Chat channel (WhatsApp/Instagram/Messenger/Email) reaches
    `handle_message()` through `channel_adapters.route_channel_message()`
    (issue #142), so this formatting applies to those channels
    automatically — `channel_adapters.py` itself never needs to call
    this function directly.
    """
    if channel_key in ("whatsapp", "instagram", "messenger"):
        return _strip_markdown(reply)
    return reply
