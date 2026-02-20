"""Omni-channel gateway for Arcturus.

This package provides the unified message bus and routing layer that
normalizes messages from all channels into MessageEnvelope format
and routes them to the appropriate agent instances.
"""

from gateway.bus import BusResult, MessageBus
from gateway.envelope import MessageEnvelope
from gateway.formatter import MessageFormatter
from gateway.router import MessageRouter, create_mock_agent

__all__ = [
    "BusResult",
    "MessageBus",
    "MessageEnvelope",
    "MessageFormatter",
    "MessageRouter",
    "create_mock_agent",
]
