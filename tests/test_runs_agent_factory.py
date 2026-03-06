"""Tests for create_runs_agent factory in gateway/router.py.

Tests cover:
- Factory returns an object with a process_message method
- process_message happy path: process_run → _fetch_run_output → completed with output
- process_message when run fails: no output → failure reply
- process_message when process_run raises → error reply
- process_message when _fetch_run_output returns no output → failed reply

All calls are mocked via unittest.mock. No real server is needed.
"""

import asyncio
import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

from gateway.envelope import MessageEnvelope
from gateway.router import create_runs_agent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_envelope(text: str = "What is the capital of France?") -> MessageEnvelope:
    return MessageEnvelope.from_webchat(
        session_id="test-session-001",
        sender_id="user-001",
        sender_name="Test User",
        text=text,
        message_id="MSG-001",
    )


def _ensure_routers_runs_mock(mock_process_run: AsyncMock):
    """Ensure `from routers.runs import process_run` resolves to our mock.

    RunsAgentAdapter.process_message does a lazy import:
        from routers.runs import process_run
    We inject a fake module into sys.modules so the import succeeds without
    pulling in the real routers.runs (which has heavy transitive deps).
    """
    fake_mod = ModuleType("routers.runs")
    fake_mod.process_run = mock_process_run  # type: ignore[attr-defined]
    # Ensure parent package exists
    if "routers" not in sys.modules:
        routers_pkg = ModuleType("routers")
        routers_pkg.__path__ = []  # type: ignore[attr-defined]
        sys.modules["routers"] = routers_pkg
    sys.modules["routers.runs"] = fake_mod


def _cleanup_routers_runs():
    """Remove the fake routers.runs from sys.modules."""
    sys.modules.pop("routers.runs", None)


# ---------------------------------------------------------------------------
# Test 1: factory returns object with process_message
# ---------------------------------------------------------------------------


def test_create_runs_agent_returns_object():
    """create_runs_agent() must return an object with an async process_message method."""

    async def _run():
        agent = await create_runs_agent("session-001")
        assert hasattr(agent, "process_message")
        assert callable(agent.process_message)

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test 2: happy path — process_run succeeds, _fetch_run_output returns output
# ---------------------------------------------------------------------------


def test_process_message_success():
    """process_message returns reply with status=completed when run succeeds."""

    async def _run():
        agent = await create_runs_agent("session-001")
        envelope = _make_envelope()

        mock_run = AsyncMock()
        mock_fetch = AsyncMock(return_value={
            "run_id": "nexus_test",
            "status": "completed",
            "output": "Paris is the capital of France.",
        })

        _ensure_routers_runs_mock(mock_run)
        try:
            with patch("gateway.router._fetch_run_output", mock_fetch):
                result = await agent.process_message(envelope)
        finally:
            _cleanup_routers_runs()

        assert result["status"] == "completed"
        assert "Paris" in result["reply"]
        assert result["run_id"].startswith("nexus_")
        mock_run.assert_awaited_once()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test 3: run fails → no output → failure reply
# ---------------------------------------------------------------------------


def test_process_message_run_failure():
    """process_message returns a failure reply when _fetch_run_output has no output."""

    async def _run():
        agent = await create_runs_agent("session-002")
        envelope = _make_envelope("crash this")

        mock_run = AsyncMock()
        mock_fetch = AsyncMock(return_value={
            "run_id": "nexus_test",
            "status": "failed",
            "output": None,
        })

        _ensure_routers_runs_mock(mock_run)
        try:
            with patch("gateway.router._fetch_run_output", mock_fetch):
                result = await agent.process_message(envelope)
        finally:
            _cleanup_routers_runs()

        assert result["status"] == "failed"
        assert isinstance(result["reply"], str)
        assert len(result["reply"]) > 0

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test 4: process_run itself errors → graceful error reply
# ---------------------------------------------------------------------------


def test_process_message_post_error():
    """process_message returns error reply when process_run raises."""

    async def _run():
        agent = await create_runs_agent("session-003")
        envelope = _make_envelope("hello")

        mock_run = AsyncMock(side_effect=Exception("connection refused"))

        _ensure_routers_runs_mock(mock_run)
        try:
            result = await agent.process_message(envelope)
        finally:
            _cleanup_routers_runs()

        assert result["status"] == "error"
        assert isinstance(result["reply"], str)
        assert len(result["reply"]) > 0

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test 5: process_run succeeds but no output produced → failed reply
# ---------------------------------------------------------------------------


def test_process_message_timeout():
    """process_message returns failed reply when run produces no output."""

    async def _run():
        agent = await create_runs_agent("session-004")
        envelope = _make_envelope("slow query")

        mock_run = AsyncMock()
        mock_fetch = AsyncMock(return_value={
            "run_id": "nexus_test",
            "status": "failed",
            "output": None,
        })

        _ensure_routers_runs_mock(mock_run)
        try:
            with patch("gateway.router._fetch_run_output", mock_fetch):
                result = await agent.process_message(envelope)
        finally:
            _cleanup_routers_runs()

        assert result["status"] == "failed"
        assert isinstance(result["reply"], str)
        assert len(result["reply"]) > 0

    asyncio.run(_run())
