"""Outbound message formatter for the Arcturus gateway.

Converts agent response text (Markdown) into the native format
required by each channel (Telegram MarkdownV2, Slack mrkdwn,
Discord markdown, WebChat HTML, or plain text fallback).
"""

import html
import re
from typing import Optional


# Characters that must be escaped in Telegram MarkdownV2
_TELEGRAM_ESCAPE_CHARS = r"\_*[]()~`>#+-=|{}.!"


def _escape_telegram_v2(text: str) -> str:
    """Escape all MarkdownV2 special characters in plain text spans."""
    return re.sub(r"([\_\*\[\]\(\)\~\`\>\#\+\-\=\|\{\}\.\!])", r"\\\1", text)


class MessageFormatter:
    """Formats outbound agent text for each target channel.

    Usage::

        formatter = MessageFormatter()
        telegram_text = formatter.format("**Hello** world!", "telegram")
        slack_text    = formatter.format("**Hello** world!", "slack")
    """

    # Mapping of channel name → internal format method name
    _CHANNEL_MAP = {
        "telegram": "_format_telegram",
        "slack": "_format_slack",
        "discord": "_format_discord",
        "webchat": "_format_webchat",
    }

    def format(self, text: str, channel: str, **kwargs) -> str:
        """Format *text* for *channel*.

        Args:
            text: Agent response in Markdown (``**bold**``, ``_italic_``,
                  backtick code, etc.).
            channel: Target channel identifier (e.g. ``"telegram"``).
            **kwargs: Reserved for future per-channel options.

        Returns:
            Formatted string ready to send on *channel*.
            Falls back to plain text for unknown channels.
        """
        method_name = self._CHANNEL_MAP.get(channel.lower(), "_format_plain")
        method = getattr(self, method_name)
        return method(text)

    # ------------------------------------------------------------------
    # Per-channel formatters
    # ------------------------------------------------------------------

    def _format_telegram(self, text: str) -> str:
        """Convert Markdown to Telegram MarkdownV2.

        Rules:
        - ``**bold**`` → ``*bold*``
        - ``_italic_`` → ``_italic_``  (same, but special chars escaped)
        - `` `code` `` → `` `code` ``
        - All MarkdownV2 reserved characters outside markup spans escaped.
        """
        # Process in passes so we don't double-escape markup delimiters.

        # 1. Extract and protect fenced code blocks ```...```
        code_blocks: list[str] = []

        def stash_code_block(m: re.Match) -> str:
            code_blocks.append(m.group(0))
            return f"\x00CODE_BLOCK_{len(code_blocks) - 1}\x00"

        text = re.sub(r"```[\s\S]*?```", stash_code_block, text)

        # 2. Extract and protect inline code `...`
        inline_codes: list[str] = []

        def stash_inline_code(m: re.Match) -> str:
            inline_codes.append(m.group(0))
            return f"\x00INLINE_CODE_{len(inline_codes) - 1}\x00"

        text = re.sub(r"`[^`]+`", stash_inline_code, text)

        # 3. Convert **bold** → *bold*  (before escaping asterisks)
        text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)

        # 4. Escape all reserved chars in the remaining plain-text spans
        #    (we do this char-by-char so markup chars we just introduced are safe)
        #    Strategy: split on our markup tokens, escape plain-text segments.
        markup_token = re.compile(r"(\*[^*]+\*|_[^_]+_)")
        parts = markup_token.split(text)
        escaped_parts = []
        for part in parts:
            if markup_token.fullmatch(part):
                escaped_parts.append(part)
            else:
                escaped_parts.append(_escape_telegram_v2(part))
        text = "".join(escaped_parts)

        # 5. Restore inline code (backtick content must NOT be escaped)
        for i, code in enumerate(inline_codes):
            text = text.replace(f"\x00INLINE_CODE_{i}\x00", code)

        # 6. Restore code blocks
        for i, block in enumerate(code_blocks):
            text = text.replace(f"\x00CODE_BLOCK_{i}\x00", block)

        return text

    def _format_slack(self, text: str) -> str:
        """Convert Markdown to Slack mrkdwn.

        Rules:
        - ``**bold**`` → ``*bold*``
        - ``_italic_`` → ``_italic_``  (same)
        - `` `code` `` → `` `code` ``  (same)
        - ``# Heading`` → ``*Heading*``  (no native headings in mrkdwn)
        - Links ``[label](url)`` → ``<url|label>``
        """
        # Headings → bold
        text = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
        # Links [label](url) → <url|label>
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", text)
        # **bold** → *bold*
        text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
        # Italic: leave _italic_ unchanged (mrkdwn uses same syntax)
        return text

    def _format_discord(self, text: str) -> str:
        """Convert Markdown to Discord markdown.

        Discord supports standard markdown for bold/italic/code/strikethrough.
        Headings are not rendered, so we convert them to bold.
        Links are auto-embedded; ``[label](url)`` works natively.
        """
        # Headings → **bold**
        text = re.sub(r"^#{1,6}\s+(.+)$", r"**\1**", text, flags=re.MULTILINE)
        # _italic_ → *italic* (Discord prefers single asterisk for italic)
        text = re.sub(r"(?<![*_])_(.+?)_(?![*_])", r"*\1*", text)
        return text

    def _format_webchat(self, text: str) -> str:
        """Convert Markdown to safe HTML for WebChat widget.

        Rules:
        - ``**bold**`` → ``<b>bold</b>``
        - ``_italic_`` → ``<i>italic</i>``
        - `` `code` `` → ``<code>code</code>``
        - Plain text HTML-encoded to prevent XSS.
        - Newlines → ``<br>``
        """
        # HTML-encode the whole string first, then re-introduce markup tags.
        # Strategy: process token by token.

        # Extract code spans first to avoid HTML-encoding them wrongly
        segments: list[tuple[str, bool]] = []  # (text, is_code)
        last = 0
        for m in re.finditer(r"`([^`]+)`", text):
            if m.start() > last:
                segments.append((text[last : m.start()], False))
            segments.append((m.group(1), True))
            last = m.end()
        if last < len(text):
            segments.append((text[last:], False))

        result_parts = []
        for segment, is_code in segments:
            if is_code:
                result_parts.append(f"<code>{html.escape(segment)}</code>")
            else:
                encoded = html.escape(segment)
                # Apply bold and italic after HTML-encoding
                encoded = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", encoded)
                encoded = re.sub(r"_(.+?)_", r"<i>\1</i>", encoded)
                result_parts.append(encoded)

        result = "".join(result_parts)
        result = result.replace("\n", "<br>")
        return result

    def _format_plain(self, text: str) -> str:
        """Strip all Markdown markup and return plain text.

        Used as the fallback for unknown channels.
        """
        # Remove fenced code blocks (keep content)
        text = re.sub(r"```[\w]*\n?([\s\S]*?)```", r"\1", text)
        # Remove inline code
        text = re.sub(r"`([^`]+)`", r"\1", text)
        # Remove headings
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        # Remove bold/italic markers
        text = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", text)
        text = re.sub(r"_(.+?)_", r"\1", text)
        # Remove links [label](url) → label
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        # Collapse extra blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
