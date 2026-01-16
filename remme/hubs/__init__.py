"""
REMME Hubs - Structured preference storage.

These hubs store typed user preferences extracted from conversations, notes, and other sources.
"""

from remme.hubs.base_hub import BaseHub
from remme.hubs.preferences_hub import PreferencesHub, get_preferences_hub
from remme.hubs.operating_context_hub import OperatingContextHub, get_operating_context_hub
from remme.hubs.soft_identity_hub import SoftIdentityHub, get_soft_identity_hub

__all__ = [
    "BaseHub",
    "PreferencesHub",
    "get_preferences_hub",
    "OperatingContextHub",
    "get_operating_context_hub",
    "SoftIdentityHub",
    "get_soft_identity_hub",
]
