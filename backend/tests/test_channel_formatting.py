"""[Omnichannel] issue #143 — channel-specific message formatting.

Proves the issue's acceptance criteria directly against
format_reply_for_channel() in isolation (not yet wired into the real
reply path — that's a separate, later issue, #151).
"""
from app.services.channel_adapters import format_reply_for_channel

_MARKDOWN_HEAVY_REPLY = (
    "Your refund has been **approved**. Here's what happens next:\n"
    "- Refund issued within *5-7 business days*\n"
    "- You'll get a confirmation email\n"
    "See our [refund policy](https://example.com/policy) for details. "
    "Reference code: `RF-1234`."
)


def test_live_chat_reply_is_byte_for_byte_unchanged():
    assert format_reply_for_channel(_MARKDOWN_HEAVY_REPLY, "live_chat") == _MARKDOWN_HEAVY_REPLY


def test_email_reply_is_unchanged():
    assert format_reply_for_channel(_MARKDOWN_HEAVY_REPLY, "email") == _MARKDOWN_HEAVY_REPLY


def test_whatsapp_reply_has_no_literal_markdown_characters():
    formatted = format_reply_for_channel(_MARKDOWN_HEAVY_REPLY, "whatsapp")
    assert "**" not in formatted
    assert "*5-7" not in formatted  # the italic marker specifically, not the words around it
    assert "`RF-1234`" not in formatted
    assert "[refund policy]" not in formatted
    assert "approved" in formatted  # the actual content survives
    assert "RF-1234" in formatted


def test_instagram_and_messenger_get_the_same_stripping_as_whatsapp():
    for channel in ("instagram", "messenger"):
        formatted = format_reply_for_channel(_MARKDOWN_HEAVY_REPLY, channel)
        assert "**" not in formatted
        assert "approved" in formatted


def test_a_plain_reply_with_no_markdown_is_unaffected_by_stripping():
    plain = "Your order shipped yesterday and should arrive Friday."
    assert format_reply_for_channel(plain, "whatsapp") == plain


def test_bullet_list_becomes_a_plain_bullet_character():
    reply = "Options:\n- Refund\n- Replacement"
    formatted = format_reply_for_channel(reply, "whatsapp")
    assert "- Refund" not in formatted
    assert "• Refund" in formatted
