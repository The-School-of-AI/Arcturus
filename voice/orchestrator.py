# voice/orchestrator.py

"""
Voice Orchestrator — coordinates wake → STT → Nexus → TTS pipeline.

Uses an utterance accumulation algorithm to detect when the user
has finished speaking before dispatching to Nexus:

  1. STT fires on_text() with sentence/clause fragments as they arrive.
  2. Each fragment is appended to a running buffer and resets a
     silence timer (default 1.5 seconds).
  3. When the timer fires (no new text for 1.5s), the full
     accumulated query is dispatched to Nexus in one shot.
  4. Nexus processes the query asynchronously. The orchestrator polls
     for completion, extracts the final output, and speaks it via TTS.

Streaming TTS (Piper)
---------------------
When the TTS backend is PiperTTSService and streaming is enabled,
the orchestrator uses a *queue-based* approach: as each Nexus node
completes, its output text is pushed into a queue.  PiperTTSService
consumes the queue and starts speaking the first complete sentence
immediately — the user hears a response **before** the full plan
finishes executing.  This dramatically reduces perceived latency.

Session Logging & Conversation Context
---------------------------------------
Every voice interaction is logged to a JSON session file under
``memory/voice_sessions/``.  Each turn records the user transcript,
TTS response text, timestamp, run_id, persona, and latency.

Conversation history is maintained within a session so the agent
has the context of prior exchanges (just like text chat sessions).
"""

import threading
import time
import re
import requests


NEXUS_BASE_URL = "http://localhost:8000/api"


# ── Tunable parameters ──────────────────────────────────────────
SILENCE_THRESHOLD_SEC = 2.0    # seconds of silence → user is done
FOLLOW_UP_WINDOW_SEC  = 30.0   # seconds to stay listening after TTS
RUN_TIMEOUT_SEC       = 300.0  # 5 min — enough for multi-step runs
PROGRESS_PING_SEC     = 45.0   # speak a reassurance if still waiting after N sec
# ────────────────────────────────────────────────────────────────


class Orchestrator:
    def __init__(self, wake_service, stt_service, agent, tts):
        self.wake = wake_service
        self.stt = stt_service
        self.agent = agent
        self.tts = tts

        # State machine (non-negotiable):
        #   IDLE → LISTENING → THINKING → SPEAKING → (INTERRUPTED) → LISTENING/IDLE
        self.state = "IDLE"
        self._lock = threading.Lock()
        self._follow_up_timer = None

        # Utterance accumulation state
        self._utterance_buffer: list[str] = []
        self._silence_timer: threading.Timer | None = None
        self._active_run_id: str | None = None

        # Instant barge-in signal: set by on_wake() so the nexus polling loop
        # unblocks immediately instead of waiting up to 500ms on evt.wait().
        self._barge_in_event = threading.Event()

        # ── Session logger (conversation context + JSON persistence) ──
        from voice.session_logger import VoiceSessionLogger
        self.session_logger = VoiceSessionLogger()

    # ─────────────── State transitions ───────────────
    def _set_state(self, new_state: str) -> None:
        """Set state and log transition (state transitions only)."""
        prev = self.state
        if prev != new_state:
            print(f"[VoiceState] {prev} → {new_state}")
            self.state = new_state

    def _set_active_run(self, run_id: str | None) -> None:
        with self._lock:
            self._active_run_id = run_id

    def _stop_active_run_async(self) -> None:
        """
        Best-effort stop of the currently active run so Nexus doesn’t keep
        executing after we’ve barged-in and intentionally won’t speak it.
        """
        with self._lock:
            run_id = self._active_run_id
        if not run_id:
            return

        def _stop():
            try:
                requests.post(
                    f"{NEXUS_BASE_URL}/runs/{run_id}/stop",
                    timeout=(1.0, 2.0),
                )
            except Exception:
                pass

        threading.Thread(target=_stop, daemon=True).start()

    # ─────────────── Wake ───────────────
    def on_wake(self, event):
        is_barge_in = event.get("type") == "BARGE_IN"

        with self._lock:
            prev_state = self.state

            if prev_state in ("SPEAKING", "THINKING"):
                print(f"⚡ [Orchestrator] Wake during {prev_state} → LISTENING")
            else:
                print("🎙️ [Orchestrator] Wake word detected. Listening...")

            self._cancel_follow_up()
            self._cancel_silence_timer()
            self._utterance_buffer.clear()
            self._set_state("LISTENING")

        # Signal nexus polling loop to unblock instantly (no 500ms wait)
        self._barge_in_event.set()

        # Cancel TTS immediately
        self.tts.cancel()

        # ── STT handling ──────────────────────────────────────────────────
        # For a normal wake-word: clear STT buffer (drop stale audio).
        # For a BARGE_IN: do NOT cancel STT — voice_wake_service already
        # pre-filled buffered speech frames and we must not wipe them.
        if not is_barge_in:
            self.stt.cancel()   # fresh wake — drop any stale buffer
        else:
            print("🎙️ [Orchestrator] Barge-in STT: keeping pre-filled frames alive")

        # Stop the in-flight Nexus run so it doesn't complete silently
        self._stop_active_run_async()

        # Start a new voice session (if coming from IDLE, i.e. fresh wake)
        if prev_state == "IDLE":
            self.session_logger.start_session()

    # ─────────────── STT fragment received ───────────────
    def on_text(self, fragment: str):
        """
        Called by STT every time a final transcript fragment arrives.
        Buffers the fragment and (re)starts the silence timer.
        """
        with self._lock:
            if self.state != "LISTENING":
                return

            self._utterance_buffer.append(fragment)
            print(f"   📝 [STT fragment] \"{fragment}\"")

            # (Re)start silence timer
            self._cancel_silence_timer()
            self._silence_timer = threading.Timer(
                SILENCE_THRESHOLD_SEC, self._on_silence_timeout
            )
            self._silence_timer.daemon = True
            self._silence_timer.start()

    # ─────────────── Silence timeout → dispatch ───────────────
    def _on_silence_timeout(self):
        """Fires when no new STT text has arrived for SILENCE_THRESHOLD_SEC."""
        with self._lock:
            if not self._utterance_buffer:
                return

            full_query = " ".join(self._utterance_buffer).strip()
            self._utterance_buffer.clear()

            if not full_query:
                return

            print(f"🗨️ [Orchestrator] Complete query: \"{full_query}\"")
            self._set_state("THINKING")

        # Choose the TTS dispatch path based on the backend
        use_streaming = self._should_use_streaming()

        if use_streaming:
            print("🔄 [Orchestrator] Using STREAMED TTS path")
            threading.Thread(
                target=self._nexus_then_speak_streamed,
                args=(full_query,),
                daemon=True,
            ).start()
        else:
            # Original path: wait for full output, then speak
            threading.Thread(
                target=self._nexus_then_speak,
                args=(full_query,),
                daemon=True,
            ).start()

    def _should_use_streaming(self) -> bool:
        """
        Check if the TTS backend supports streaming and it's enabled.
        Returns True for PiperTTSService or Azure TTSService when their
        respective streaming_enabled flag is set in config.
        """
        try:
            from voice.config import VOICE_CONFIG
        except Exception:
            print("⚠️ [Orchestrator] _should_use_streaming: failed to import VOICE_CONFIG")
            return False

        # Check Piper
        from voice.piper_tts_service import PiperTTSService
        if isinstance(self.tts, PiperTTSService):
            result = VOICE_CONFIG.get("piper_tts", {}).get("streaming_enabled", False)
            print(f"🔍 [Orchestrator] TTS=Piper, streaming_enabled={result}")
            return result

        # Check Azure TTSService
        from voice.tts_service import TTSService
        if isinstance(self.tts, TTSService):
            result = VOICE_CONFIG.get("tts", {}).get("streaming_enabled", False)
            print(f"🔍 [Orchestrator] TTS=Azure, streaming_enabled={result}")
            return result

        print(f"⚠️ [Orchestrator] Unknown TTS type: {type(self.tts)}")
        return False

    # ─────────────── Nexus → event → TTS ───────────────

    # Varied acknowledgment phrases so it doesn't feel robotic
    _ACK_PHRASES = [
        "Let me look into that for you.",
        "On it! Searching now.",
        "Great question! Let me find out.",
        "Give me a moment, I'm researching that.",
        "Searching for that right now.",
        "Let me dig into that.",
        "Working on it!",
        "One moment, please.",
    ]

    def _nexus_then_speak(self, query: str):
        """
        1. POST query to Nexus  →  get run_id
        2. Speak a brief acknowledgment while agent works
        3. Wait on in-process Event (instant wake-up when run finishes)
        4. Speak the result through TTS
        5. Log the turn to VoiceSessionLogger
        6. Enter follow-up window
        """
        import random
        from shared.state import register_run_waiter, pop_run_result

        t_start = time.time()
        print(f"🔗 [Orchestrator] Dispatching to Nexus: \"{query}\"")

        # Inject conversation history into the Nexus query
        history_prefix = self.session_logger.get_history_prompt(max_turns=8)
        enriched_query = f"{history_prefix}{query}" if history_prefix else query

        run_id = self._start_nexus_run(enriched_query)
        if not run_id:
            print("❌ [Orchestrator] Failed to start Nexus run.")
            # Log failed attempt
            self.session_logger.log_turn(
                user_transcript=query,
                tts_text=None,
                run_id=None,
                persona=self.tts.active_persona,
                latency_ms=None,
                source="nexus",
                extra={"error": "Failed to start Nexus run"},
            )
            self._enter_follow_up()
            return
        self._set_active_run(run_id)
        # Clear any stale barge-in signal from a previous turn
        self._barge_in_event.clear()

        # Register the Event for this run_id ASAP
        evt = register_run_waiter(run_id)
        print(f"📡 [Orchestrator] Event registered for run {run_id}.")

        # Speak brief acknowledgment while agent works
        # Set state to SPEAKING so VAD echo suppression kicks in
        ack = random.choice(self._ACK_PHRASES)
        with self._lock:
            self._set_state("SPEAKING")
        self.tts.speak(ack)
        with self._lock:
            if self.state == "SPEAKING":
                self._set_state("THINKING")
            else:
                # Genuine barge-in happened during ack
                pop_run_result(run_id)
                print("⚡ [Orchestrator] Barge-in during ack — aborting.")
                self._stop_active_run_async()
                return

        print(f"⏳ [Orchestrator] Waiting for Nexus run {run_id}...")

        # Wait for completion — check barge-in every 0.5s,
        # speak a progress ping every PROGRESS_PING_SEC to reassure the user.
        deadline = time.time() + RUN_TIMEOUT_SEC
        last_ping = time.time()
        _PROGRESS_PHRASES = [
            "Still working on it, almost there!",
            "This one's taking a moment, hang tight.",
            "Still researching, bear with me.",
            "Almost done, just crunching the details.",
        ]
        import itertools
        _ping_cycle = itertools.cycle(_PROGRESS_PHRASES)

        while not evt.is_set() and time.time() < deadline:
            with self._lock:
                if self.state != "THINKING":
                    pop_run_result(run_id)  # clean up
                    print("⚡ [Orchestrator] Barge-in during processing — skipping TTS.")
                    self._stop_active_run_async()
                    return

            # Periodic spoken ping so the user knows we’re still alive
            now = time.time()
            if now - last_ping >= PROGRESS_PING_SEC:
                ping = next(_ping_cycle)
                print(f"📣 [Orchestrator] Progress ping: {ping}")
                # Set state to SPEAKING so VAD echo suppression kicks in
                with self._lock:
                    self._set_state("SPEAKING")
                self.tts.speak(ping)
                with self._lock:
                    if self.state == "SPEAKING":
                        self._set_state("THINKING")
                last_ping = time.time()
                # Re-check event — run may have completed during ping
                if evt.is_set():
                    break

            # Wake every 50ms to check _barge_in_event for instant abort.
            # Also check every 0.5s for state (catches edge cases).
            self._barge_in_event.wait(timeout=0.05)
            if self._barge_in_event.is_set():
                with self._lock:
                    if self.state != "THINKING":
                        pop_run_result(run_id)
                        print("⚡ [Orchestrator] Barge-in (instant) during processing — skipping TTS.")
                        self._stop_active_run_async()
                        self._set_active_run(None)
                        return
                # state is still THINKING (false alarm) — clear and keep going
                self._barge_in_event.clear()

        if not evt.is_set():
            pop_run_result(run_id)
            print(f"⏰ [Orchestrator] Run {run_id} timed out after {RUN_TIMEOUT_SEC}s")
            self.session_logger.log_turn(
                user_transcript=query,
                tts_text=None,
                run_id=run_id,
                persona=self.tts.active_persona,
                latency_ms=(time.time() - t_start) * 1000,
                source="nexus",
                extra={"error": f"Timed out after {RUN_TIMEOUT_SEC}s"},
            )
            self._enter_follow_up()
            self._set_active_run(None)
            return

        # Grab the result
        final_text = pop_run_result(run_id)
        print(f"📥 [Orchestrator] Got result for run {run_id}: "
              f"{len(final_text) if final_text else 0} chars")

        # Check barge-in one more time
        with self._lock:
            if self.state != "THINKING":
                print("⚡ [Orchestrator] Barge-in during processing — skipping TTS.")
                return

        latency_ms = (time.time() - t_start) * 1000
        spoken_text = None

        if final_text and final_text.strip():
            spoken_text = self._markdown_to_speech(final_text)
            print(f"🔊 [Orchestrator] TTS input ({len(spoken_text)} chars): "
                  f"\"{spoken_text[:100]}...\"")
            with self._lock:
                self._set_state("SPEAKING")
            self.tts.speak(spoken_text)
        else:
            print("⚠️ [Orchestrator] No speakable output from Nexus.")

        # ── Log the turn ──
        self.session_logger.log_turn(
            user_transcript=query,
            tts_text=spoken_text,
            run_id=run_id,
            persona=self.tts.active_persona,
            latency_ms=latency_ms,
            source="nexus",
        )

        # Enter follow-up listening window (only if not barged-in)
        with self._lock:
            if self.state in ("SPEAKING", "THINKING"):
                pass  # will enter follow-up below
            else:
                return  # barge-in happened during TTS
        self._enter_follow_up()
        self._set_active_run(None)

    def _start_nexus_run(self, query: str, stream: bool = False) -> str | None:
        """POST /api/runs and return the run_id, or None on failure."""
        url = f"{NEXUS_BASE_URL}/runs"
        # Production hardening:
        # - /api/runs should return immediately with a run_id, but during dev reloads
        #   or brief restarts, localhost can transiently time out.
        # - Retry a couple times quickly so voice UX doesn’t randomly “miss” runs.
        for attempt in range(3):
            try:
                # Separate connect/read timeouts (seconds).
                # Read timeout can be short because create_run is meant to be fast.
                resp = requests.post(
                    url,
                    json={
                        "query": query,
                        "source": "voice",
                        "stream": stream
                    },
                    timeout=(1.0, 4.0),
                )
                if resp.ok:
                    data = resp.json()
                    run_id = data.get("id")
                    print(f"🚀 [Orchestrator] Nexus run started → ID: {run_id}")
                    return run_id
                else:
                    print(f"⚠️ [Orchestrator] Nexus returned {resp.status_code}: {resp.text}")
                    return None
            except Exception as e:
                if attempt == 2:
                    print(f"❌ [Orchestrator] Failed to reach Nexus: {e}")
                    break
                time.sleep(0.2 * (2 ** attempt))
        return None

    # ─────────────── Extract speakable text ───────────────
    def _extract_speakable_text(self, run_data: dict) -> str | None:
        """
        Walk the Nexus run graph and extract a concise, TTS-friendly
        response from the agent output.

        Priority:
          1. FormatterAgent markdown_report → strip markdown
          2. Any node with a substantial string output → strip markdown
          3. Fallback: "I've completed the task."
        """
        graph = run_data.get("graph", {})
        nodes = graph.get("nodes", [])

        if not nodes:
            return "I've completed your request, but I don't have a summary to share."

        # 1. Look for FormatterAgent output (the polished report)
        for node in nodes:
            node_data = node.get("data", {})
            agent_type = node_data.get("agent", "")
            output = node_data.get("output", {})

            if not output or not isinstance(output, dict):
                continue

            if "Format" in agent_type or agent_type == "FormatterAgent":
                md = output.get("markdown_report") or output.get("formatted_report")
                if not md:
                    for k, v in output.items():
                        if ("report" in k.lower() or "formatted" in k.lower()) and isinstance(v, str):
                            md = v
                            break
                if md and len(md) > 50:
                    return self._markdown_to_speech(md)

        # 2. Fallback: find the last completed node with a substantial output
        for node in reversed(nodes):
            node_data = node.get("data", {})
            status = node_data.get("status", "")
            output = node_data.get("output", {})
            node_id = node.get("id", "")

            if node_id == "ROOT" or status != "completed":
                continue

            if isinstance(output, dict):
                # Find the largest string value
                best = ""
                for v in output.values():
                    if isinstance(v, str) and len(v) > len(best):
                        best = v
                if len(best) > 50:
                    return self._markdown_to_speech(best)

            elif isinstance(output, str) and len(output) > 50:
                return self._markdown_to_speech(output)

        return "I've completed your request."

    @staticmethod
    def _markdown_to_speech(md_text: str) -> str:
        """
        Convert markdown to clean, speakable plain text.
        Strips headers, bold/italic markers, links, code blocks, etc.
        Keeps it concise for voice — truncates at ~800 chars.
        """
        text = md_text

        # ── Guard: never speak raw Python exception strings ─────────────────
        # If the entire text looks like an exception (NameError, TypeError, etc.)
        # replace it with a graceful spoken fallback.
        _EXCEPTION_PATTERN = re.compile(
            r'^(NameError|TypeError|ValueError|AttributeError|KeyError|'
            r'IndexError|RuntimeError|ImportError|ModuleNotFoundError|'
            r'ZeroDivisionError|AssertionError|OSError|FileNotFoundError|'
            r'StopIteration|GeneratorExit|SystemExit|Exception|BaseException|'
            r'Traceback \(most recent call last\))',
            re.MULTILINE
        )
        if _EXCEPTION_PATTERN.search(text.strip()):
            print(f"⚠️ [Orchestrator] Suppressing error string from TTS: {text[:120]!r}")
            return "I ran into a small issue while processing that. Please try again."

        # ── Step 1: Remove code blocks (before anything else) ────────────────
        text = re.sub(r'```[\s\S]*?```', '', text)
        text = re.sub(r'`[^`]+`', '', text)

        # ── Step 2: Remove markdown images ────────────────────────────────────
        text = re.sub(r'!\[[^\]]*\]\([^\)]+\)', '', text)

        # ── Step 3: Convert links → label only ───────────────────────────────
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

        # ── Step 4: Strip header markers (# ## ### at line start) ────────────
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

        # ── Step 5: Strip bold/italic wrappers (*** ** * _ __ ___) ──────────
        # Must do longest match first (*** before ** before *)
        text = re.sub(r'\*{3}([^*]+)\*{3}', r'\1', text)
        text = re.sub(r'\*{2}([^*]+)\*{2}', r'\1', text)
        text = re.sub(r'\*([^*\n]+)\*',     r'\1', text)
        text = re.sub(r'_{3}([^_]+)_{3}',   r'\1', text)
        text = re.sub(r'_{2}([^_]+)_{2}',   r'\1', text)
        text = re.sub(r'_([^_\n]+)_',       r'\1', text)

        # ── Step 6: Remove horizontal rules ──────────────────────────────────
        text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)

        # ── Step 7: Remove bullet/list markers ───────────────────────────────
        text = re.sub(r'^[\s]*[-*+]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)

        # ── Step 8: Remove table formatting ──────────────────────────────────
        text = re.sub(r'\|', ' ', text)
        text = re.sub(r'^[-:]+\s*$', '', text, flags=re.MULTILINE)

        # ── Step 9: Remove LLM placeholder boilerplate ───────────────────────
        text = re.sub(r'\[?[Pp]laceholder\b[^\]\n]*\]?\.?', '', text)
        text = re.sub(
            r'\[(?:Add|Insert|Include|Enter|TODO|TBD|Content goes here)[^\]]*\]',
            '', text, flags=re.IGNORECASE
        )

        # ── Step 10: Remove "Captain" in all spoken forms ────────────────────
        # "Captain: ...", "Captain," "Captain." "Captain!" and bare "Captain"
        # anywhere in the text (it's an internal agent persona label, not speech).
        text = re.sub(r'\bCaptain\b[\s:,.\!]*', '', text, flags=re.IGNORECASE)

        # ── Step 11: Scrub any surviving bare symbol characters ───────────────
        # After all the paired-syntax removals above, orphaned # and * chars
        # (e.g. a lone asterisk used as emphasis without a closing pair) must go.
        text = re.sub(r'#+', '', text)   # bare hash(es) anywhere
        text = re.sub(r'\*+', '', text)  # bare asterisk(s) anywhere

        # ── Step 12: Whitespace cleanup ───────────────────────────────────────
        text = re.sub(r'^[ \t]+', '', text, flags=re.MULTILINE)  # leading spaces on lines
        text = re.sub(r'[ \t]{2,}', ' ', text)                   # multiple spaces → one
        text = re.sub(r'^\s*$', '', text, flags=re.MULTILINE)    # blank lines
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()

        # ── Step 13: Truncate for voice (keep it conversational) ─────────────
        if len(text) > 800:
            cut = text[:800].rfind('.')
            if cut > 400:
                text = text[:cut + 1]
            else:
                text = text[:800] + "..."

        return text


    # ─────────────── Nexus → Streamed TTS (Piper / Azure) ───────────────

    def _nexus_then_speak_streamed(self, query: str):
        """
        Streaming TTS path (works with both Piper and Azure):

        1. POST query to Nexus → get run_id
        2. Speak a brief acknowledgment
        3. Register a stream queue for this run_id
        4. Start TTS.speak_streamed() in a parallel thread
           (it blocks while consuming the queue)
        5. Wait for Nexus completion via Event — as nodes complete,
           the runs router pushes text chunks into the stream queue
        6. When the run finishes, send the sentinel to flush remaining text
        7. Wait for TTS to finish, log the turn, enter follow-up
        """
        import random
        from shared.state import (
            register_run_waiter, pop_run_result,
            register_stream_queue, finish_stream, pop_stream_queue,
        )

        t_start = time.time()
        print(f"🔗 [Orchestrator] [STREAMED] Dispatching to Nexus: \"{query}\"")

        # Inject conversation history
        history_prefix = self.session_logger.get_history_prompt(max_turns=8)
        enriched_query = f"{history_prefix}{query}" if history_prefix else query

        run_id = self._start_nexus_run(enriched_query)
        if not run_id:
            print("❌ [Orchestrator] Failed to start Nexus run.")
            self.session_logger.log_turn(
                user_transcript=query,
                tts_text=None,
                run_id=None,
                persona=self.tts.active_persona,
                latency_ms=None,
                source="nexus",
                extra={"error": "Failed to start Nexus run"},
            )
            self._enter_follow_up()
            return
        self._set_active_run(run_id)
        # Clear any stale barge-in signal from a previous turn
        self._barge_in_event.clear()

        # Register both: Event for completion + Queue for streaming chunks
        evt = register_run_waiter(run_id)
        stream_q = register_stream_queue(run_id)
        print(f"📡 [Orchestrator] Event + Stream Queue registered for run {run_id}")

        # Speak acknowledgment
        ack = random.choice(self._ACK_PHRASES)
        with self._lock:
            self._set_state("SPEAKING")
        self.tts.speak(ack)
        with self._lock:
            if self.state == "SPEAKING":
                self._set_state("THINKING")
            else:
                pop_run_result(run_id)
                pop_stream_queue(run_id)
                print("⚡ [Orchestrator] Barge-in during ack — aborting streamed path.")
                self._stop_active_run_async()
                self._set_active_run(None)
                return

        print(f"⏳ [Orchestrator] [STREAMED] Waiting for Nexus run {run_id}...")

        # Start the TTS consumer thread — it will block on stream_q
        tts_done_event = threading.Event()
        tts_started_event = threading.Event()  # Signal that TTS is actively consuming
        spoken_text_holder = []  # mutable container to capture spoken text

        def _tts_consumer():
            """Consume stream_q via TTS.speak_streamed()."""
            try:
                with self._lock:
                    self._set_state("SPEAKING")
                tts_started_event.set()  # Signal that we've entered SPEAKING state
                print(f"🎙️ [Orchestrator] TTS consumer STARTED — calling speak_streamed()")
                self.tts.speak_streamed(stream_q)
                print(f"✅ [Orchestrator] TTS consumer FINISHED — speak_streamed() returned")
            except Exception as e:
                import traceback
                print(f"❌ [Orchestrator] TTS consumer error: {e}")
                traceback.print_exc()
            finally:
                tts_done_event.set()
                print(f"🏁 [Orchestrator] TTS done event SET")

        tts_thread = threading.Thread(target=_tts_consumer, daemon=True)
        tts_thread.start()
        print(f"🚀 [Orchestrator] TTS consumer thread started for run {run_id}")
        
        # Give the TTS thread a moment to start consuming (prevents race condition)
        # If it doesn't start in 2 seconds, we have a problem
        if not tts_started_event.wait(timeout=2.0):
            print(f"⚠️ [Orchestrator] TTS consumer thread failed to start within 2s for run {run_id}")

        # Wait for the Nexus run to complete (or timeout / barge-in)
        deadline = time.time() + RUN_TIMEOUT_SEC

        while not evt.is_set() and time.time() < deadline:
            with self._lock:
                cur_state = self.state
                if cur_state not in ("THINKING", "SPEAKING"):
                    pop_run_result(run_id)
                    finish_stream(run_id)
                    pop_stream_queue(run_id)
                    print(f"⚡ [Orchestrator] Barge-in during streamed processing (state={cur_state}) — aborting.")
                    self._stop_active_run_async()
                    self._set_active_run(None)
                    return
            # Wake every 50ms on _barge_in_event for instant abort on barge-in.
            self._barge_in_event.wait(timeout=0.05)
            if self._barge_in_event.is_set():
                with self._lock:
                    cur_state = self.state
                if cur_state not in ("THINKING", "SPEAKING"):
                    pop_run_result(run_id)
                    finish_stream(run_id)
                    pop_stream_queue(run_id)
                    print(f"⚡ [Orchestrator] Barge-in (instant) during streamed processing — aborting.")
                    self._stop_active_run_async()
                    self._set_active_run(None)
                    return
                # state is still valid (spurious) — clear and keep going
                self._barge_in_event.clear()

        if not evt.is_set():
            # Timed out
            finish_stream(run_id)
            pop_run_result(run_id)
            print(f"⏰ [Orchestrator] Run {run_id} timed out after {RUN_TIMEOUT_SEC}s")
            
            # Wait briefly for TTS consumer to finish before cleanup (max 5s for timeout case)
            tts_done_event.wait(timeout=5.0)
            pop_stream_queue(run_id)
            
            self.session_logger.log_turn(
                user_transcript=query,
                tts_text=None,
                run_id=run_id,
                persona=self.tts.active_persona,
                latency_ms=(time.time() - t_start) * 1000,
                source="nexus",
                extra={"error": f"Timed out after {RUN_TIMEOUT_SEC}s"},
            )
            self._enter_follow_up()
            self._set_active_run(None)
            return

        # Run completed — grab the full result for logging
        full_result = pop_run_result(run_id)
        print(f"📥 [Orchestrator] [STREAMED] Run {run_id} completed: "
              f"{len(full_result) if full_result else 0} chars")
        print(f"🔍 [Orchestrator] stream_q size at completion: ~{stream_q.qsize()} items")
        print(f"🔍 [Orchestrator] tts.is_speaking={self.tts.is_speaking}, tts_done_event={tts_done_event.is_set()}")

        # The stream should already have the sentinel pushed by runs.py
        # but finish it defensively (only pushes if queue still registered)
        finish_stream(run_id)
        
        # CRITICAL: Do NOT pop_stream_queue yet! process_run may still be pushing chunks.
        # Must wait for TTS consumer to finish reading before cleaning up.

        # Wait for TTS to finish speaking all buffered sentences
        print(f"⏳ [Orchestrator] Waiting for TTS consumer to finish (up to 60s)...")
        tts_done_event.wait(timeout=60.0)
        print(f"✅ [Orchestrator] TTS consumer finished (done={tts_done_event.is_set()})")
        
        # Now safe to clean up the stream queue after TTS consumer is done
        pop_stream_queue(run_id)

        latency_ms = (time.time() - t_start) * 1000

        # Log the turn
        spoken_text = self._markdown_to_speech(full_result) if full_result else None
        self.session_logger.log_turn(
            user_transcript=query,
            tts_text=spoken_text,
            run_id=run_id,
            persona=self.tts.active_persona,
            latency_ms=latency_ms,
            source="nexus-streamed",
        )

        # Enter follow-up listening window
        with self._lock:
            if self.state in ("SPEAKING", "THINKING"):
                pass
            else:
                return  # barge-in happened during TTS
        self._enter_follow_up()
        self._set_active_run(None)

    # ─────────────── Interrupt ───────────────
    def interrupt(self):
        """Called by VAD barge-in or external interrupt. Cancels TTS and enters LISTENING."""
        with self._lock:
            prev = self.state
            # Non-negotiable: only allow barge-in interruption in SPEAKING state.
            if prev != "SPEAKING":
                return
            self._set_state("INTERRUPTED")
            print(f"⚡ [Orchestrator] Interrupt: {prev} → INTERRUPTED")
            self._cancel_follow_up()
            self._cancel_silence_timer()
            self._utterance_buffer.clear()
            self._set_state("LISTENING")

        # Cancel TTS outside lock (stop_speaking_async may block briefly)
        self.tts.cancel()
        self.stt.cancel()  # drop stale STT buffer
        # Stop the active Nexus run so it doesn't complete silently.
        self._stop_active_run_async()

    # ─────────────── Helpers ───────────────
    def _enter_follow_up(self):
        """Transition to LISTENING with a follow-up timeout."""
        with self._lock:
            self._set_state("LISTENING")
            self._cancel_follow_up()
            self._follow_up_timer = threading.Timer(
                FOLLOW_UP_WINDOW_SEC, self._go_idle
            )
            self._follow_up_timer.daemon = True
            self._follow_up_timer.start()

    def _go_idle(self):
        with self._lock:
            if self.state == "LISTENING":
                print("💤 [Orchestrator] Follow-up window expired. Going IDLE.")
                self._set_state("IDLE")
        # Flush the voice session log when going idle
        self.session_logger.end_session()

    def _cancel_follow_up(self):
        if self._follow_up_timer:
            self._follow_up_timer.cancel()
            self._follow_up_timer = None

    def _cancel_silence_timer(self):
        if self._silence_timer:
            self._silence_timer.cancel()
            self._silence_timer = None

    def _cancel_all(self):
        self.stt.cancel()
        self.tts.cancel()
        self.agent.cancel()
        # Flush any open voice session on shutdown
        self.session_logger.end_session()