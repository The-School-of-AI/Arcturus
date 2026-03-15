"""P01 HC10h — P95 message processing latency benchmark.

Verifies that P95 latency of bus.roundtrip() stays under 2500 ms
(HC10h target: < 2.5s message processing latency).

Uses create_mock_agent so the measurement captures gateway overhead only
(envelope construction, routing, session affinity, formatting, outbox
delivery) without network I/O to a real agent or real channel adapter.

Run:
    uv run python -m pytest tests/test_p01_latency.py -v
"""

import asyncio
import statistics
import time

import pytest

from channels.webchat import WebChatAdapter
from gateway.bus import MessageBus
from gateway.envelope import MessageEnvelope
from gateway.formatter import MessageFormatter
from gateway.router import MessageRouter, create_mock_agent

# HC10h target (milliseconds)
_P95_TARGET_MS = 2500
# Number of roundtrips to sample
_SAMPLE_SIZE = 100


def _make_bus() -> MessageBus:
    formatter = MessageFormatter()
    router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)
    return MessageBus(
        router=router,
        formatter=formatter,
        adapters={"webchat": WebChatAdapter()},
    )


def _make_envelope(i: int) -> MessageEnvelope:
    return MessageEnvelope.from_webchat(
        session_id=f"bench-session-{i % 10}",  # 10 sessions → exercises affinity
        sender_id=f"user-{i % 10}",
        sender_name="Bench User",
        text=f"Benchmark message number {i}",
        message_id=f"bench-{i:04d}",
    )


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


def test_p95_roundtrip_latency_under_target():
    """P95 of bus.roundtrip() across 100 calls must be < 2500 ms (HC10h)."""

    async def _run():
        bus = _make_bus()
        latencies_ms: list[float] = []

        for i in range(_SAMPLE_SIZE):
            envelope = _make_envelope(i)
            t0 = time.perf_counter()
            await bus.roundtrip(envelope)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            latencies_ms.append(elapsed_ms)

        return latencies_ms

    latencies_ms = asyncio.run(_run())

    latencies_ms.sort()
    p50 = statistics.median(latencies_ms)
    p95_index = int(len(latencies_ms) * 0.95) - 1
    p95 = latencies_ms[max(p95_index, 0)]
    p99_index = int(len(latencies_ms) * 0.99) - 1
    p99 = latencies_ms[max(p99_index, 0)]

    print(
        f"\nLatency over {_SAMPLE_SIZE} roundtrips — "
        f"P50: {p50:.1f}ms  P95: {p95:.1f}ms  P99: {p99:.1f}ms  "
        f"max: {max(latencies_ms):.1f}ms"
    )

    assert p95 < _P95_TARGET_MS, (
        f"P95 latency {p95:.1f}ms exceeds HC10h target of {_P95_TARGET_MS}ms"
    )
