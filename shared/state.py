# Shared State Module
# This module holds global state that is shared across all routers

from pathlib import Path

# Project root for path resolution in routers
PROJECT_ROOT = Path(__file__).parent.parent

# === Lazy-loaded dependencies ===
# These will be initialized when first accessed or during api.py lifespan

# Global state - shared across routers
active_loops = {}

# ── Voice global speaking/cancel state (production-grade barge-in) ──────────
# Non-negotiable contract:
#   - is_tts_speaking: global "TTS audio may be playing" indicator
#   - cancel_tts_event: global cancellation signal (checked inside TTS loops)
#
# Notes:
# - This is intentionally thread-based (voice pipeline uses threads today).
# - We keep cancellation separate from orchestrator.state (IDLE/LISTENING/...)
#   so both can be used safely across modules without circular dependencies.
import time
import threading

_tts_state_lock = threading.Lock()

# True from TTS start → until TTS playback loop exits (even if cancel requested).
is_tts_speaking: bool = False

# Global cancellation event checked by TTS streaming loops.
cancel_tts_event: threading.Event = threading.Event()

# During the grace window we suppress barge-in detection completely to avoid
# TTS attack-phase echo leakage (speaker → mic).
_tts_barge_in_grace_until_monotonic: float = 0.0


def tts_mark_start(*, grace_ms: int = 300) -> None:
    """Mark TTS as speaking and open a barge-in grace window."""
    global is_tts_speaking, _tts_barge_in_grace_until_monotonic
    now = time.monotonic()
    with _tts_state_lock:
        is_tts_speaking = True
        cancel_tts_event.clear()
        _tts_barge_in_grace_until_monotonic = now + (grace_ms / 1000.0)


def tts_mark_stop() -> None:
    """Mark TTS as no longer speaking (called when playback loop exits)."""
    global is_tts_speaking, _tts_barge_in_grace_until_monotonic
    with _tts_state_lock:
        is_tts_speaking = False
        _tts_barge_in_grace_until_monotonic = 0.0
        # Do NOT clear cancel_tts_event here; callers may want to observe it.


def tts_request_cancel() -> None:
    """Request immediate TTS cancellation (safe to call from any thread)."""
    cancel_tts_event.set()


def tts_in_barge_in_grace_window() -> bool:
    """True if we are still within the post-TTS-start grace window."""
    now = time.monotonic()
    with _tts_state_lock:
        return bool(is_tts_speaking) and now < _tts_barge_in_grace_until_monotonic


def tts_is_speaking() -> bool:
    """Thread-safe read of global TTS speaking state."""
    with _tts_state_lock:
        return bool(is_tts_speaking)

# ── Voice pipeline: instant run-result signaling ───────────────
# When process_run finishes, it stores the output here and sets
# the Event so the voice orchestrator wakes up immediately.
# Thread-safe: both the orchestrator thread and the async event loop
# can access this concurrently.
import threading

_run_results_lock = threading.Lock()
run_results: dict = {}           # run_id → {"output": str, "event": Event}

def register_run_waiter(run_id: str):
    """
    Create an Event the orchestrator can wait on.
    
    Race-safe: if signal_run_complete already fired for this run_id
    (the run finished before we registered), we return a pre-set Event
    so the orchestrator unblocks immediately.
    """
    with _run_results_lock:
        existing = run_results.get(run_id)
        if existing and existing.get("output") is not None:
            # Signal already arrived! Create a pre-set Event.
            evt = threading.Event()
            evt.set()
            existing["event"] = evt
            print(f"📡 [Signal] Waiter for {run_id} — result already available!")
            return evt

        # Normal case: register and wait
        evt = threading.Event()
        run_results[run_id] = {"output": None, "event": evt}
        return evt

def signal_run_complete(run_id: str, output_text: str):
    """Called by process_run when done — wakes the orchestrator instantly."""
    with _run_results_lock:
        out_len = len(output_text) if output_text else 0
        entry = run_results.get(run_id)
        if entry and entry.get("event"):
            # Waiter is registered — set the result and wake it up
            entry["output"] = output_text
            entry["event"].set()
            print(f"🔔 [Signal] Run {run_id} complete → voice waiter notified ({out_len} chars)")
        else:
            # No waiter yet (or non-voice run) — store result for later pickup
            run_results[run_id] = {"output": output_text, "event": None}
            print(f"🔔 [Signal] Run {run_id} complete → stored for pickup ({out_len} chars)")

def pop_run_result(run_id: str) -> str | None:
    """Retrieve and remove the result for a run."""
    with _run_results_lock:
        entry = run_results.pop(run_id, None)
        if entry:
            return entry.get("output")
        return None


# ── Streaming text chunks for Piper TTS / Azure TTS ────────────────────────
# Instead of waiting for the full output, the orchestrator can
# receive text chunk-by-chunk via a queue and start speaking
# immediately (sentence-level streaming).
import queue as _queue_mod

_stream_queues_lock = threading.Lock()
_stream_queues: dict = {}         # run_id → queue.Queue
_stream_chunk_counts: dict = {}   # run_id → int  (# chunks pushed so far)

def register_stream_queue(run_id: str) -> _queue_mod.Queue:
    """
    Register a Queue the orchestrator will consume from.
    process_run pushes text chunks; the voice pipeline speaks them
    as they arrive.
    """
    with _stream_queues_lock:
        q = _queue_mod.Queue()
        _stream_queues[run_id] = q
        _stream_chunk_counts[run_id] = 0
        print(f"📡 [Stream] Queue registered for run {run_id}")
        return q

def push_stream_chunk(run_id: str, text_chunk: str):
    """Push a text chunk to the voice stream queue (if registered)."""
    with _stream_queues_lock:
        q = _stream_queues.get(run_id)
        if q:
            _stream_chunk_counts[run_id] = _stream_chunk_counts.get(run_id, 0) + 1
    if q:
        q.put(text_chunk)
        print(f"📡 [Stream] Chunk pushed for {run_id}: "
              f"{len(text_chunk)} chars")
    else:
        print(f"⚠️ [Stream] CRITICAL: Queue for {run_id} not found! "
              f"Text not pushed: {text_chunk[:100] if len(text_chunk) > 100 else text_chunk}")

def get_stream_chunk_count(run_id: str) -> int:
    """Return how many text chunks have been pushed for this run (0 if none)."""
    with _stream_queues_lock:
        return _stream_chunk_counts.get(run_id, 0)

def finish_stream(run_id: str):
    """Signal that no more chunks will arrive for this run."""
    with _stream_queues_lock:
        q = _stream_queues.get(run_id)
    if q:
        q.put(None)  # sentinel
        print(f"📡 [Stream] Stream finished for {run_id}")

def pop_stream_queue(run_id: str) -> _queue_mod.Queue | None:
    """Remove and return the stream queue for a run (cleanup)."""
    with _stream_queues_lock:
        _stream_chunk_counts.pop(run_id, None)
        return _stream_queues.pop(run_id, None)

def has_stream_queue(run_id: str) -> bool:
    """Check if a streaming queue is registered for a run."""
    with _stream_queues_lock:
        return run_id in _stream_queues


# MCP instance - will be started in api.py lifespan
_multi_mcp = None

def get_multi_mcp():
    """Get the MultiMCP instance, creating it if needed."""
    global _multi_mcp
    if _multi_mcp is None:
        from mcp_servers.multi_mcp import MultiMCP
        _multi_mcp = MultiMCP()
    return _multi_mcp

# RemMe / Vector store instance (provider-agnostic via get_vector_store)
_remme_store = None

def get_remme_store():
    """Get the vector store instance via abstraction layer. Uses get_vector_store()."""
    global _remme_store
    if _remme_store is None:
        import os
        from memory.vector_store import get_vector_store
        _remme_store = get_vector_store()
    return _remme_store

# RemMe extractor instance
_remme_extractor = None

def get_remme_extractor():
    """Get the RemmeExtractor instance, creating it if needed."""
    global _remme_extractor
    if _remme_extractor is None:
        from remme.extractor import RemmeExtractor
        _remme_extractor = RemmeExtractor()
    return _remme_extractor

# Skill Manager instance
_skill_manager = None

def get_skill_manager():
    """Get the SkillManager instance, creating/initializing it if needed."""
    global _skill_manager
    if _skill_manager is None:
        from core.skills.manager import SkillManager
        _skill_manager = SkillManager()
        _skill_manager.initialize()
    return _skill_manager

# Agent Runner instance
_agent_runner = None

def get_agent_runner():
    """Get the AgentRunner instance, creating it if needed."""
    global _agent_runner
    if _agent_runner is None:
        from agents.base_agent import AgentRunner
        _agent_runner = AgentRunner(get_multi_mcp())
    return _agent_runner

# Studio Storage instance
_studio_storage = None

def get_studio_storage():
    """Get the StudioStorage instance, creating it if needed."""
    global _studio_storage
    if _studio_storage is None:
        from core.studio.storage import StudioStorage
        _studio_storage = StudioStorage()
    return _studio_storage

# Global settings state
settings = {}

# Nexus MessageBus instance — shared across all routers
_message_bus = None

def get_message_bus():
    """Get the Nexus MessageBus instance, creating it if needed.

    Wires together: MessageFormatter + MessageRouter (mock agent) +
    TelegramAdapter + WebChatAdapter.
    """
    global _message_bus
    if _message_bus is None:
        from gateway.bus import MessageBus
        from gateway.formatter import MessageFormatter
        from gateway.router import MessageRouter, create_mock_agent
        from channels.telegram import TelegramAdapter
        from channels.webchat import WebChatAdapter
        formatter = MessageFormatter()
        router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)
        _message_bus = MessageBus(
            router=router,
            formatter=formatter,
            adapters={
                "telegram": TelegramAdapter(),
                "webchat": WebChatAdapter(),
            },
        )
    return _message_bus

# Canvas components
_canvas_ws = None
_canvas_runtime = None

def get_canvas_ws():
    """Get the CanvasWSHandler instance."""
    global _canvas_ws
    if _canvas_ws is None:
        from canvas.ws_handler import CanvasWSHandler
        _canvas_ws = CanvasWSHandler()
    return _canvas_ws

def get_canvas_runtime():
    """Get the CanvasRuntime instance."""
    global _canvas_runtime
    if _canvas_runtime is None:
        from canvas.runtime import CanvasRuntime
        _canvas_runtime = CanvasRuntime(get_canvas_ws())
    return _canvas_runtime
