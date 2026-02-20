"""Unit tests for gateway.formatter.MessageFormatter.

Covers per-channel text formatting: Telegram MarkdownV2, Slack mrkdwn,
Discord markdown, WebChat HTML, and plain-text fallback.
"""

import pytest

from gateway.formatter import MessageFormatter


@pytest.fixture
def fmt() -> MessageFormatter:
    return MessageFormatter()


# ---------------------------------------------------------------------------
# Telegram MarkdownV2
# ---------------------------------------------------------------------------


def test_format_telegram_bold(fmt: MessageFormatter):
    """**bold** Markdown → *bold* MarkdownV2."""
    result = fmt.format("**hello**", "telegram")
    assert "*hello*" in result
    # Should NOT leave double-asterisks
    assert "**hello**" not in result


def test_format_telegram_escapes_special_chars(fmt: MessageFormatter):
    """Reserved MarkdownV2 chars outside markup must be escaped."""
    # The period, exclamation, and dash are reserved in Telegram MarkdownV2
    result = fmt.format("Hello world. Good-bye!", "telegram")
    assert r"\." in result
    assert r"\!" in result
    assert r"\-" in result


def test_format_telegram_inline_code_not_escaped(fmt: MessageFormatter):
    """Backtick code spans must survive without escaping their contents."""
    result = fmt.format("`some.code`", "telegram")
    # The dot inside the code span must NOT be escaped
    assert "`some.code`" in result


def test_format_telegram_italic_preserved(fmt: MessageFormatter):
    """_italic_ stays as _italic_ in MarkdownV2."""
    result = fmt.format("_italic_", "telegram")
    assert "_italic_" in result


# ---------------------------------------------------------------------------
# Slack mrkdwn
# ---------------------------------------------------------------------------


def test_format_slack_bold(fmt: MessageFormatter):
    """**bold** → *bold* for Slack mrkdwn."""
    result = fmt.format("**hello**", "slack")
    assert result == "*hello*"


def test_format_slack_link(fmt: MessageFormatter):
    """[label](url) → <url|label> for Slack mrkdwn."""
    result = fmt.format("[Arcturus](https://example.com)", "slack")
    assert "<https://example.com|Arcturus>" in result


def test_format_slack_heading_becomes_bold(fmt: MessageFormatter):
    """Headings (#, ##) are converted to *bold* in Slack."""
    result = fmt.format("# Section Title", "slack")
    assert "*Section Title*" in result
    assert "#" not in result


# ---------------------------------------------------------------------------
# Discord
# ---------------------------------------------------------------------------


def test_format_discord_bold_passthrough(fmt: MessageFormatter):
    """**bold** is kept as-is for Discord (standard Markdown)."""
    result = fmt.format("**hello**", "discord")
    assert "**hello**" in result


def test_format_discord_heading_becomes_bold(fmt: MessageFormatter):
    """Headings are converted to **bold** for Discord."""
    result = fmt.format("## Title", "discord")
    assert "**Title**" in result


# ---------------------------------------------------------------------------
# WebChat HTML
# ---------------------------------------------------------------------------


def test_format_webchat_bold(fmt: MessageFormatter):
    """**bold** → <b>bold</b> for WebChat."""
    result = fmt.format("**world**", "webchat")
    assert "<b>world</b>" in result


def test_format_webchat_html_encodes_plain_text(fmt: MessageFormatter):
    """Plain-text special HTML chars are encoded to prevent XSS."""
    result = fmt.format("3 < 5 & 7 > 2", "webchat")
    assert "<" not in result.replace("<b>", "").replace("</b>", "").replace("<br>", "")
    assert "&lt;" in result or "&amp;" in result  # at least one entity encoded


def test_format_webchat_code_span(fmt: MessageFormatter):
    """`code` → <code>code</code> for WebChat."""
    result = fmt.format("`my_code`", "webchat")
    assert "<code>my_code</code>" in result


# ---------------------------------------------------------------------------
# Plain-text fallback
# ---------------------------------------------------------------------------


def test_format_plain_strips_bold(fmt: MessageFormatter):
    """**bold** → bold with all markup stripped."""
    result = fmt.format("**bold**", "plain")
    assert result == "bold"


def test_format_plain_strips_inline_code(fmt: MessageFormatter):
    """`code` → code."""
    result = fmt.format("`code`", "plain")
    assert result == "code"


def test_format_unknown_channel_falls_back_to_plain(fmt: MessageFormatter):
    """Unknown channel identifiers fall back to plain-text formatting."""
    result = fmt.format("**bold** _italic_ `code`", "unknown_channel_xyz")
    # All markup should be stripped
    assert "**" not in result
    assert "_" not in result
    assert "`" not in result
    assert "bold" in result
    assert "italic" in result
    assert "code" in result


def test_format_plain_strips_link(fmt: MessageFormatter):
    """[label](url) → label."""
    result = fmt.format("[click here](https://example.com)", "plain")
    assert result == "click here"
