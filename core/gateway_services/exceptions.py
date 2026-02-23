from __future__ import annotations


class IntegrationDependencyUnavailable(RuntimeError):
    """Raised when a required integration dependency is not configured/available."""


class UpstreamIntegrationError(RuntimeError):
    """Raised when an upstream integration call fails in a controlled way."""
