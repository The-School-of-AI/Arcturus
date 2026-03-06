"""Unit tests for MessageRouter group activation policies.

Tests the two activation modes:
- ``"always-on"``: every message is routed regardless of content.
- ``"mention-only"``: only messages containing the bot mention token are routed;
  others are short-circuited with ``routed=False``.
"""

import asyncio

from gateway.envelope import MessageEnvelope
from gateway.router import MessageRouter, create_mock_agent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_telegram_envelope(text: str, chat_id: str = "99") -> MessageEnvelope:
    return MessageEnvelope.from_telegram(
        chat_id=chat_id,
        sender_id="42",
        sender_name="Alice",
        text=text,
        message_id="msg-ga-tg",
    )


def _make_slack_envelope(text: str) -> MessageEnvelope:
    return MessageEnvelope.from_slack(
        channel_id="C04KYFS5DV2",
        sender_id="U999",
        sender_name="Bob",
        text=text,
        message_id="msg-ga-sl",
    )


def _make_webchat_envelope(text: str) -> MessageEnvelope:
    return MessageEnvelope.from_webchat(
        session_id="sess-ga",
        sender_id="u1",
        sender_name="Carol",
        text=text,
        message_id="msg-ga-wc",
    )


# ---------------------------------------------------------------------------
# Test: always-on channel always routes
# ---------------------------------------------------------------------------


def test_always_on_routes_without_mention():
    """always-on channel must route even when the message has no bot mention."""

    async def _run():
        router = MessageRouter(
            agent_factory=create_mock_agent,
            group_activation={"webchat": "always-on"},
        )
        env = _make_webchat_envelope("Hello, can you help?")
        result = await router.route(env)
        assert result["routed"] is True
        assert result["status"] == "success"
        assert result["agent_response"] is not None

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test: mention-only channel skips without mention
# ---------------------------------------------------------------------------


def test_mention_only_skips_without_mention():
    """mention-only channel must NOT route when the bot mention is absent."""

    async def _run():
        router = MessageRouter(
            agent_factory=create_mock_agent,
            group_activation={"telegram": "mention-only"},
        )
        env = _make_telegram_envelope("Hey everyone, what's up?")
        result = await router.route(env)
        assert result["routed"] is False
        assert result["status"] == "skipped"
        assert result["reason"] == "mention_required"
        assert result["agent_response"] is None

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test: mention-only channel routes when mention is present
# ---------------------------------------------------------------------------


def test_mention_only_routes_with_mention():
    """mention-only channel MUST route when the bot mention is present."""

    async def _run():
        router = MessageRouter(
            agent_factory=create_mock_agent,
            group_activation={"telegram": "mention-only"},
        )
        env = _make_telegram_envelope("@arcturus what is the weather today?")
        result = await router.route(env)
        assert result["routed"] is True
        assert result["status"] == "success"
        assert result["agent_response"] is not None

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test: mention check is case-insensitive
# ---------------------------------------------------------------------------


def test_mention_only_case_insensitive():
    """Mention matching must be case-insensitive (@Arcturus, @ARCTURUS, etc.)."""

    async def _run():
        router = MessageRouter(
            agent_factory=create_mock_agent,
            group_activation={"slack": "mention-only"},
        )
        for mention in ["@Arcturus", "@ARCTURUS", "@ArCtUrUs"]:
            env = _make_slack_envelope(f"{mention} help me!")
            result = await router.route(env)
            assert result["routed"] is True, f"Failed for mention variant: {mention}"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test: channels not in group_activation default to always-on
# ---------------------------------------------------------------------------


def test_unconfigured_channel_defaults_to_always_on():
    """A channel absent from group_activation must default to always-on."""

    async def _run():
        # No webchat key in group_activation
        router = MessageRouter(
            agent_factory=create_mock_agent,
            group_activation={"telegram": "mention-only"},
        )
        env = _make_webchat_envelope("Just a plain message, no mention")
        result = await router.route(env)
        assert result["routed"] is True

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test: custom bot_mention token
# ---------------------------------------------------------------------------


def test_custom_bot_mention_token():
    """Custom bot_mention should override the default @arcturus token."""

    async def _run():
        router = MessageRouter(
            agent_factory=create_mock_agent,
            group_activation={"telegram": "mention-only"},
            bot_mention="@mybot",
        )
        # Default @arcturus should NOT trigger routing
        env_no = _make_telegram_envelope("@arcturus help!")
        result_no = await router.route(env_no)
        assert result_no["routed"] is False

        # Custom @mybot SHOULD trigger routing
        env_yes = _make_telegram_envelope("@mybot help!")
        result_yes = await router.route(env_yes)
        assert result_yes["routed"] is True

    asyncio.run(_run())
