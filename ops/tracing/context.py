"""
WATCHTOWER: ContextVar for propagating plan node context to llm.generate spans.
"""
from contextlib import contextmanager
from contextvars import ContextVar

_watchtower_span_context: ContextVar[dict] = ContextVar("watchtower_span_context", default={})


@contextmanager
def set_span_context(ctx: dict):
    """Set span context (agent, node_id) for llm.generate spans. Resets on exit."""
    token = _watchtower_span_context.set(ctx)
    try:
        yield
    finally:
        _watchtower_span_context.reset(token)


def get_span_context() -> dict:
    """Return current span context for llm.generate attribute enrichment."""
    return _watchtower_span_context.get()
