"""Omni-channel adapters for Arcturus communication gateway.

This package provides channel adapters for various messaging platforms
(Telegram, WebChat, Slack, Discord, WhatsApp, etc.) that normalize
inbound messages into MessageEnvelope format and send outbound responses.
"""

from channels.base import ChannelAdapter

__all__ = ["ChannelAdapter"]
