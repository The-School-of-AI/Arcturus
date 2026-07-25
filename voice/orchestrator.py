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

        # ── Dictation session (set when state == DICTATING) ──────────────
        from voice.dictation_service import DictationSession
        self._dictation_session: DictationSession | None = None

        # ── Session logger (conversation context + JSON persistence) ──
        from voice.session_logger import VoiceSessionLogger
        self.session_logger = VoiceSessionLogger()

        # ── Intent gate: classify utterances before routing to any pipeline ──
        from voice.intent_gate import IntentRouter
        self.intent_router = IntentRouter(self)

        # ── Event loop reference (injected by api.py lifespan) ────────────
        # asyncio.get_event_loop() from a background thread returns the wrong
        # loop in Python 3.10+.  api.py stores the real FastAPI loop here.
        self._event_loop = None

        # ── Polling flag: set True on wake, cleared by GET /voice/wake ────
        self.wake_detected = False

    # ─────────────── Event bus helper ─────────────────────────────────────
    def _publish(self, event_type: str, data: dict) -> None:
        """
        Fire-and-forget: publish an event onto the FastAPI event loop from
        any thread (wake word, STT, silence timeout — all run in bg threads).

        Uses self._event_loop when available (injected at startup), otherwise
        falls back to asyncio.get_event_loop() for compatibility.
        """
        import asyncio
        from core.event_bus import event_bus
        try:
            loop = self._event_loop
            if loop is None or loop.is_closed():
                # Fallback: try the running loop (works if called from async ctx)
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.get_event_loop()
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    event_bus.publish(event_type, "orchestrator", data), loop
                )
            else:
                print(f"[Orchestrator._publish] No running loop — event {event_type!r} dropped")
        except Exception as exc:
            print(f"[Orchestrator._publish] Error publishing {event_type!r}: {exc}")

    # ─────────────── State transitions ───────────────
    def _set_state(self, new_state: str, silent: bool = False) -> None:
        """Set state and log transition.

        Args:
            new_state: Target state string.
            silent:    When True, update the internal state without
                       broadcasting a ``voice_state`` SSE event.  Use this
                       for transient bookkeeping states (e.g. echo-suppression
                       SPEAKING during a nexus ack) that must NOT flash on the
                       frontend UI.
        """
        prev = self.state
        if prev != new_state:
            print(f"[VoiceState] {prev} → {new_state}{' (silent)' if silent else ''}")
            self.state = new_state
            if not silent:
                self._publish("voice_state", {"state": new_state})

    # ─────────────── TTS speak wrapper ─────────────────────────────────────
    def _speak(self, text: str, source: str = "agent") -> None:
        """
        Speak via TTS **and** broadcast a ``voice_tts`` SSE event so the
        Echo panel can display what Arcturus said.

        Args:
            text:   The plain-text string to speak.
            source: Label for the UI (e.g. ``"answer"``, ``"clarification"``,
                    ``"navigation"``, ``"dictation"``).
        """
        self._publish("voice_tts", {"text": text, "source": source})
        self.tts.speak(text)

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

            # ── DICTATING guard ───────────────────────────────────────────
            # While dictation is active, user speech is expected and will
            # continuously trigger the barge-in / VAD system.  Ignore ALL
            # wake / barge-in events so we never tear down the dictation
            # session.  Only an explicit stop_dictation() call exits this mode.
            if prev_state == "DICTATING":
                return

            if prev_state in ("SPEAKING", "THINKING"):
                print(f"⚡ [Orchestrator] Wake during {prev_state} → LISTENING")
            else:
                print("[Orchestrator] Wake word detected. Listening...")

            self._cancel_follow_up()
            self._cancel_silence_timer()
            self._utterance_buffer.clear()
            self._set_state("LISTENING")
            self.wake_detected = True   # consumed by GET /voice/wake polling

        # Signal nexus polling loop to unblock instantly (no 500ms wait)
        self._barge_in_event.set()

        try:
            self._publish("voice_wake", {"barge_in": is_barge_in})
        except Exception:
            pass

        # Cancel TTS immediately
        self.tts.cancel()

        # ── STT handling ──────────────────────────────────────────────────
        # For a normal wake-word: clear STT buffer (drop stale audio).
        # For a BARGE_IN: do NOT cancel STT — voice_wake_service already
        # pre-filled buffered speech frames and we must not wipe them.
        if not is_barge_in:
            self.stt.cancel()   # fresh wake — drop any stale buffer
        else:
            print("[Orchestrator] Barge-in STT: keeping pre-filled frames alive")

        # Stop the in-flight Nexus run so it doesn't complete silently
        active_run = self._active_run_id
        if active_run:
            self._publish("voice_nexus_run", {"active": False, "run_id": active_run, "reason": "barge_in"})
        self._stop_active_run_async()

        # Start or resume a voice session.
        # If coming from IDLE with no existing session, start a new one.
        # If a session already exists (user continuing conversation), keep it.
        if prev_state == "IDLE" and not self.session_logger.session_id:
            self.session_logger.start_session()


    # ─────────────── STT fragment received ───────────────
    def on_text(self, fragment: str):
        """
        Called by STT every time a final transcript fragment arrives.
        - In DICTATING state: routed to the active DictationSession.
        - In LISTENING state: buffered and (re)starts the silence timer.
        """
        with self._lock:
            if self.state == "DICTATING":
                if not self._dictation_session:
                    return

                # ── Voice stop commands ───────────────────────────────────
                # Check for stop phrases BEFORE pushing to the session so
                # the command itself is not recorded as dictation content.
                _stop_phrases = (
                    "stop dictation",
                    "end dictation",
                    "stop recording",
                    "end recording",
                    "finish dictation",
                    "stop",          # bare "stop" is unambiguous inside dictation
                )
                _frag_lower = fragment.strip().lower().rstrip(".,!?")
                if any(_frag_lower == phrase or _frag_lower.endswith(phrase)
                       for phrase in _stop_phrases):
                    print(f"⏹️ [Dictation] Stop command detected: \"{fragment}\"")
                    # Run stop_dictation() in a daemon thread so the TTS
                    # announcement and file-save don't block the STT callback.
                    threading.Thread(
                        target=self.stop_dictation,
                        daemon=True,
                    ).start()
                    return

                # Normal fragment — push to document buffer
                self._dictation_session.push_fragment(fragment)
                return

            if self.state != "LISTENING":
                return

            self._utterance_buffer.append(fragment)
            print(f"   📝 [STT fragment] \"{fragment}\"")
            
            try:
                full_text = " ".join(self._utterance_buffer)
                self._publish("voice_stt", {"fragment": fragment, "full_text": full_text})
            except Exception:
                pass

            # (Re)start silence timer
            self._cancel_silence_timer()
            self._silence_timer = threading.Timer(
                SILENCE_THRESHOLD_SEC, self._on_silence_timeout
            )
            self._silence_timer.daemon = True
            self._silence_timer.start()

    # ─────────────── Dictation Mode ───────────────

    def start_dictation(self) -> str:
        """
        Enter DICTATING mode: STT stays active, but every transcript fragment
        goes to a DictationSession document buffer instead of Nexus.

        Returns the new session_id.  TTS is silenced; any in-progress run
        is cancelled.
        """
        import uuid
        from voice.dictation_service import DictationSession

        with self._lock:
            prev_state = self.state
            session_id = f"dict_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
            self._dictation_session = DictationSession(session_id)
            self._utterance_buffer.clear()
            self._cancel_silence_timer()
            self._set_state("DICTATING")

        print(f"🎤 [Orchestrator] Dictation STARTED (session: {session_id}, prev: {prev_state})")

        # Cancel any TTS and ongoing Nexus run
        self.tts.cancel()
        self._stop_active_run_async()
        self._speak("Dictation mode on. Speak freely, I'm listening.", source="dictation")

        return session_id

    def stop_dictation(self) -> dict:
        """
        Exit DICTATING mode.  Finalises the document, saves it to disk,
        and returns a summary dict:
            {
              "session_id": str,
              "text": str,          # full plain-text document
              "word_count": int,
              "saved_to": str,      # file path
            }
        After this call the Orchestrator returns to IDLE (ready for wake word).
        """
        with self._lock:
            if self.state != "DICTATING" or not self._dictation_session:
                return {"error": "Not currently in dictation mode"}
            session = self._dictation_session
            self._dictation_session = None
            self._set_state("IDLE")

        saved_path = session.finish()
        doc = session.get_document()
        
        # Also save to Notes as requested
        session.save_to_notes()
        
        try:
            self._publish("voice_note_saved", {"session_id": session.session_id})
        except Exception:
            pass

        print(f"⏹️ [Orchestrator] Dictation STOPPED — {session.word_count} words.")
        self._speak(f"Dictation stopped. {session.word_count} words saved in Notes.", source="dictation")

        return {
            "session_id": session.session_id,
            "text": doc,
            "word_count": session.word_count,
            "saved_to": saved_path,
        }

    def get_dictation_status(self) -> dict:
        """Return the current dictation state and live document preview."""
        with self._lock:
            if self.state != "DICTATING" or not self._dictation_session:
                return {"active": False}
            session = self._dictation_session

        text = session.get_document()
        return {
            "active": True,
            "session_id": session.session_id,
            "started_at": session.started_at,
            "fragment_count": session.fragment_count,
            "word_count": session.word_count,
            "preview": text[:500] + ("..." if len(text) > 500 else ""),
            "text": text,
        }

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

            print(f"🗨️ [Orchestrator] Complete utterance: \"{full_query}\"")

        # ── Intent Gate ────────────────────────────────────────────────
        # Classify the utterance first.  Only non-DICTATION paths set
        # state=THINKING and enter the Nexus pipeline.
        # IntentRouter handles state transitions internally.
        self._set_state("THINKING")
        self.intent_router.route(full_query)

    def _should_use_streaming(self) -> bool:
        """
        Check if the TTS backend supports streaming and it's enabled.
        Returns True for KokoroTTSService, PiperTTSService, or Azure
        TTSService when their respective streaming_enabled flag is set.
        """
        try:
            from voice.config import VOICE_CONFIG
        except Exception:
            print("⚠️ [Orchestrator] _should_use_streaming: failed to import VOICE_CONFIG")
            return False

        # Check Kokoro
        try:
            from voice.kokoro_tts_service import KokoroTTSService
            if isinstance(self.tts, KokoroTTSService):
                result = VOICE_CONFIG.get("kokoro_tts", {}).get("streaming_enabled", True)
                print(f"🔍 [Orchestrator] TTS=Kokoro, streaming_enabled={result}")
                return result
        except ImportError:
            pass

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

    # ─────────────── Nexus mid-run clarification ───────────────

    def _check_nexus_clarification(self, run_id: str) -> dict | None:
        """
        Poll the live Nexus run graph for a ClarificationAgent node that is
        in ``waiting_input`` status.

        Returns a dict  ``{"node_id": str, "message": str, "options": list}``
        when a pending clarification is found, otherwise ``None``.

        This is safe to call every ~2 s from the wait loop — it is a cheap
        HTTP GET that hits the session file on disk.
        """
        try:
            resp = requests.get(
                f"{NEXUS_BASE_URL}/runs/{run_id}",
                timeout=(1.0, 3.0),
            )
            if not resp.ok:
                return None
            data = resp.json()
            nodes = data.get("graph", {}).get("nodes", [])
            for node in nodes:
                if (
                    node.get("data", {}).get("status") == "waiting_input"
                    and node.get("data", {}).get("agent") == "ClarificationAgent"
                ):
                    output = node.get("data", {}).get("output") or {}
                    message = output.get("clarificationMessage", "")
                    options = output.get("options", [])
                    if message:
                        return {
                            "node_id": node.get("id", ""),
                            "message": message,
                            "options": options,
                        }
        except Exception as e:
            print(f"⚠️ [Orchestrator] _check_nexus_clarification error: {e}")
        return None

    def _handle_nexus_clarification(self, run_id: str, clarification: dict) -> bool:
        """
        Voice round-trip for a mid-run ClarificationAgent pause:

          1. Speak the clarification question (+ options if any) via TTS.
          2. Set state → LISTENING and wait for the user's STT response
             (up to CLARIFICATION_ANSWER_TIMEOUT_SEC).
          3. POST the answer to  ``/api/runs/{run_id}/input``.
          4. Return True if an answer was collected and submitted, False on
             barge-in / timeout / stop.

        State machine contract
        ----------------------
        Enters:  THINKING
        Exits:   THINKING  (run resumes) or LISTENING (barge-in / abort)
        """
        message = clarification["message"]
        options = clarification.get("options", [])

        # Build spoken prompt
        spoken_q = message
        if options:
            spoken_q += ". Options are: " + "; ".join(options) + "."
        spoken_q = self._markdown_to_speech(spoken_q)

        print(f"❓ [Orchestrator] Nexus clarification: {spoken_q[:120]}")

        # ── Speak the question ─────────────────────────────────────────────
        with self._lock:
            self._set_state("SPEAKING")
        self._speak(spoken_q, source="clarification")
        with self._lock:
            if self.state != "SPEAKING":
                # Barge-in during the question — abort
                print("⚡ [Orchestrator] Barge-in during clarification question — aborting.")
                return False
            self._set_state("LISTENING")
            self._utterance_buffer.clear()

        # ── Wait for the user's answer via STT ────────────────────────────
        # We wait synchronously here (we're already in a daemon thread).
        # A threading.Event is set by a one-shot silence timer created below.
        answer_event = threading.Event()
        captured_answer: list[str] = []  # mutable container

        CLARIFICATION_ANSWER_TIMEOUT_SEC = 20.0  # user has 20 s to answer
        CHECK_INTERVAL = 0.1  # poll every 100 ms

        elapsed = 0.0
        while elapsed < CLARIFICATION_ANSWER_TIMEOUT_SEC:
            # Check for barge-in / state change
            with self._lock:
                if self.state not in ("LISTENING", "SPEAKING"):
                    print("⚡ [Orchestrator] State changed during clarification listen — aborting.")
                    return False

            # Check if silence timer fired (utterance_buffer was cleared by the
            # orchestrator's own silence timer path inside _on_silence_timeout).
            # We detect the answer by watching _utterance_buffer transitions:
            # on_text() fills it, _on_silence_timeout() drains it.
            # Since _on_silence_timeout sets state→THINKING and calls route(),
            # we intercept the *raw* buffer just before it's drained.
            # Simpler approach: just watch state — when it flips to THINKING
            # the silence timer already fired with user's answer in the buffer.
            # But we want the buffer BEFORE it is cleared.  So we watch for
            # a non-empty buffer + a configurable quiet period instead.

            with self._lock:
                buf = list(self._utterance_buffer)

            if buf:
                # Wait one more silence-threshold to give STT time to finish
                time.sleep(SILENCE_THRESHOLD_SEC + 0.1)
                with self._lock:
                    # Grab whatever was accumulated; _on_silence_timeout may
                    # have already cleared it — in that case we missed it.
                    final_buf = list(self._utterance_buffer)
                    if not final_buf and buf:
                        # Timeout already fired — use what we saw earlier
                        final_buf = buf
                if final_buf:
                    captured_answer.append(" ".join(final_buf).strip())
                    break

            self._barge_in_event.wait(timeout=CHECK_INTERVAL)
            if self._barge_in_event.is_set():
                print("⚡ [Orchestrator] Barge-in during clarification listening — aborting.")
                return False
            elapsed += CHECK_INTERVAL

        if not captured_answer or not captured_answer[0]:
            print("⏰ [Orchestrator] No clarification answer received within timeout.")
            # Speak a timeout notice and return to THINKING so the run can
            # be cancelled or the user can try again.
            self._speak("I didn't catch your answer. Please try again.", source="clarification")
            with self._lock:
                self._set_state("THINKING")
            return False

        answer_text = captured_answer[0]
        print(f"✅ [Orchestrator] Clarification answer: \"{answer_text}\"")

        # ── POST the answer to Nexus ───────────────────────────────────────
        try:
            resp = requests.post(
                f"{NEXUS_BASE_URL}/runs/{run_id}/input",
                json={"node_id": clarification["node_id"], "response": answer_text},
                timeout=(1.0, 4.0),
            )
            if resp.ok:
                print(f"📨 [Orchestrator] Clarification submitted for run {run_id}.")
                with self._lock:
                    self._set_state("THINKING")
                return True
            else:
                print(f"⚠️ [Orchestrator] /runs/{run_id}/input returned {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"❌ [Orchestrator] Failed to submit clarification: {e}")

        with self._lock:
            self._set_state("THINKING")
        return False

    # ─────────────── Nexus → event → TTS ───────────────

    # ─────────────── Direct LLM Chat (fast voice path) ───────────────

    def _direct_chat_then_speak(self, query: str):
        """
        Fast voice conversation path — calls Ollama directly, bypasses Nexus.

        1. Build a short conversation prompt from session history
        2. Call Ollama synchronously via HTTP
        3. Speak the response via TTS
        4. Enter follow-up listening window

        This is ~5-10x faster than the Nexus pipeline for simple Q&A.
        """
        import asyncio

        t_start = time.time()
        print(f"💬 [Orchestrator] Direct chat: \"{query}\"")

        # Build conversation messages from session history
        history = self.session_logger.get_conversation_history()
        messages = [
            {
                "role": "system",
                "content": (
                    "You are Arcturus, a helpful voice assistant. "
                    "Keep your responses concise and conversational — "
                    "you are speaking aloud, not writing. "
                    "Aim for 1-3 sentences unless the user asks for detail. "
                    "Do not use markdown, code blocks, or bullet points."
                ),
            }
        ]
        # Add recent history (last 8 turns)
        for msg in history[-16:]:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })
        # Add the current query
        messages.append({"role": "user", "content": query})

        # Call Ollama directly via HTTP (synchronous — we're in a bg thread)
        from config.settings_loader import reload_settings
        fresh = reload_settings()
        agent_cfg = fresh.get("agent", {})
        model = agent_cfg.get("default_model", "gemma3:12b")
        provider = agent_cfg.get("model_provider", "ollama")

        ollama_url = fresh.get("ollama", {}).get("base_url", "http://127.0.0.1:11434")

        response_text = None
        try:
            if provider == "ollama":
                resp = requests.post(
                    f"{ollama_url}/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": False,
                    },
                    timeout=(5.0, 60.0),
                )
                if resp.ok:
                    data = resp.json()
                    response_text = data.get("message", {}).get("content", "")
                else:
                    print(f"⚠️ [DirectChat] Ollama returned {resp.status_code}: {resp.text[:200]}")
            else:
                # Fallback: use ModelManager for non-Ollama providers
                from core.model_manager import ModelManager
                mm = ModelManager(model, provider=provider)
                loop = self._event_loop
                if loop and loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(
                        mm.generate_text("\n".join(m["content"] for m in messages)),
                        loop,
                    )
                    response_text = future.result(timeout=30.0)
        except Exception as e:
            print(f"❌ [DirectChat] LLM call failed: {e}")

        latency_ms = (time.time() - t_start) * 1000

        # Check barge-in
        with self._lock:
            if self.state != "THINKING":
                print("⚡ [DirectChat] Barge-in during thinking — skipping TTS.")
                return

        if response_text and response_text.strip():
            spoken = self._markdown_to_speech(response_text)
            print(f"💬 [DirectChat] Response ({latency_ms:.0f}ms): \"{spoken[:100]}...\"")
            with self._lock:
                self._set_state("SPEAKING")
            self._speak(spoken, source="answer")
        else:
            print("⚠️ [DirectChat] No response from LLM.")
            with self._lock:
                self._set_state("SPEAKING")
            self._speak("Sorry, I didn't get a response. Could you try again?", source="agent")

        # Log the turn
        self.session_logger.log_turn(
            user_transcript=query,
            tts_text=response_text,
            run_id=None,
            persona=self.tts.active_persona,
            latency_ms=latency_ms,
            source="direct_chat",
        )

        self._enter_follow_up()

    # ─────────────── Nexus pipeline (heavy multi-agent path) ───────────────

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

        # Speak brief acknowledgment BEFORE starting the Nexus run so it appears
        # above the user query in the conversation UI.
        ack = random.choice(self._ACK_PHRASES)
        with self._lock:
            self._set_state("SPEAKING", silent=True)
        self._speak(ack, source="agent")
        with self._lock:
            if self.state == "SPEAKING":
                self._set_state("THINKING")
            else:
                # Genuine barge-in happened during ack
                print("⚡ [Orchestrator] Barge-in during ack — aborting.")
                return

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

        # Publish nexus-run-started event so the UI can display it
        self._publish("voice_nexus_run", {"active": True, "run_id": run_id, "query": query})

        print(f"⏳ [Orchestrator] Waiting for Nexus run {run_id}...")

        # Wait for completion — check clarification + barge-in every 50ms,
        # speak a progress ping every PROGRESS_PING_SEC to reassure the user.
        deadline = time.time() + RUN_TIMEOUT_SEC
        last_ping = time.time()
        last_clarification_check = time.time()
        CLARIFICATION_CHECK_INTERVAL = 2.0   # poll run graph every 2 s
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

            now = time.time()

            # ── Nexus mid-run clarification check ─────────────────────────
            if now - last_clarification_check >= CLARIFICATION_CHECK_INTERVAL:
                last_clarification_check = now
                clarification = self._check_nexus_clarification(run_id)
                if clarification:
                    print(f"🔔 [Orchestrator] ClarificationAgent waiting — entering voice clarification loop.")
                    answered = self._handle_nexus_clarification(run_id, clarification)
                    if not answered:
                        pop_run_result(run_id)
                        self._stop_active_run_async()
                        self._set_active_run(None)
                        return
                    last_ping = time.time()
                    last_clarification_check = time.time()
                    continue

            # ── Periodic spoken ping ───────────────────────────────────────
            if now - last_ping >= PROGRESS_PING_SEC:
                ping = next(_ping_cycle)
                print(f"📣 [Orchestrator] Progress ping: {ping}")
                # We are about to speak a ping.
                with self._lock:
                    self._set_state("SPEAKING", silent=True)
                self.tts.speak(ping)
                with self._lock:
                    if self.state == "SPEAKING":
                        # Return to THINKING immediately after ping
                        self._set_state("THINKING")
                last_ping = time.time()
                if evt.is_set():
                    break

            # Wake every 50ms to check _barge_in_event for instant abort.
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
            self._publish("voice_nexus_run", {"active": False, "run_id": run_id, "reason": "timeout"})
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
            self._speak(spoken_text, source="answer")
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

        # Nexus run is complete — notify UI
        self._publish("voice_nexus_run", {"active": False, "run_id": run_id, "reason": "completed"})

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
        # Catch common exception names and traceback headers.
        # We look for these keywords anywhere as distinct words to avoid leakage
        # if the LLM wraps them in conversational filler.
        _EXCEPTION_KEYWORDS = (
            r'NameError|TypeError|ValueError|AttributeError|KeyError|IndexError|'
            r'RuntimeError|ImportError|ModuleNotFoundError|ZeroDivisionError|'
            r'SyntaxError|IndentationError|UnboundLocalError|RecursionError|'
            r'AssertionError|OSError|FileNotFoundError|Exception|Traceback'
        )
        _EXCEPTION_RE = re.compile(rf'\b({_EXCEPTION_KEYWORDS})\b', re.IGNORECASE)

        # If a short string contains a technical exception name, it's likely a failure report.
        if (len(text) < 300 and _EXCEPTION_RE.search(text)) or "traceback (most recent call last)" in text.lower():
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

        # Speak acknowledgment BEFORE starting the Nexus run
        ack = random.choice(self._ACK_PHRASES)
        with self._lock:
            self._set_state("SPEAKING", silent=True)
        self._speak(ack, source="agent")
        with self._lock:
            if self.state == "SPEAKING":
                self._set_state("THINKING")
            else:
                print("⚡ [Orchestrator] Barge-in during ack — aborting streamed path acknowledgment.")
                return

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

        print(f"⏳ [Orchestrator] [STREAMED] Waiting for Nexus run {run_id}...")

        # Start the TTS consumer thread — it will block on stream_q
        tts_done_event = threading.Event()
        tts_started_event = threading.Event()  # Signal that TTS is actively consuming
        spoken_text_holder = []  # mutable container to capture spoken text

        def _tts_consumer():
            """Consume stream_q via TTS.speak_streamed()."""
            try:
                # Do NOT set SPEAKING state yet. We wait until the first sentence is ready.
                tts_started_event.set() 
                print(f"[Orchestrator] TTS consumer STARTED — calling speak_streamed()")
                
                # Pass a callback to publish sentences as they are spoken
                def _on_sentence(text):
                    if text and text.strip():
                        # We have actual text to speak! Transition to SPEAKING state now.
                        with self._lock:
                            if self.state == "THINKING":
                                self._set_state("SPEAKING")
                        self._publish("voice_tts", {"text": text.strip(), "source": "answer"})
                
                self.tts.speak_streamed(stream_q, on_sentence_callback=_on_sentence)
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
        last_clarification_check_s = time.time()
        CLARIFICATION_CHECK_INTERVAL_S = 2.0

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

            now_s = time.time()

            # ── Nexus mid-run clarification check (streamed path) ──────────
            # Only run when TTS is not actively consuming (cur_state == THINKING)
            # to avoid speaking the question over an in-progress stream.
            if cur_state == "THINKING" and now_s - last_clarification_check_s >= CLARIFICATION_CHECK_INTERVAL_S:
                last_clarification_check_s = now_s
                clarification_s = self._check_nexus_clarification(run_id)
                if clarification_s:
                    print(f"🔔 [Orchestrator] [STREAMED] ClarificationAgent waiting — entering voice clarification loop.")
                    answered_s = self._handle_nexus_clarification(run_id, clarification_s)
                    if not answered_s:
                        pop_run_result(run_id)
                        finish_stream(run_id)
                        pop_stream_queue(run_id)
                        self._stop_active_run_async()
                        self._set_active_run(None)
                        return
                    last_clarification_check_s = time.time()
                    continue

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
            # Non-negotiable: only allow interruption in SPEAKING state.
            # DICTATING is also excluded — continuous user speech is expected there.
            if prev not in ("SPEAKING",):
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
        # Save session to disk but keep conversation history so the user can
        # continue the conversation by pressing mic again.
        self.session_logger.save_session()

    def manual_stop(self) -> dict:
        """
        Called when the user presses the mic button a second time to stop
        recording.  Immediately processes whatever has been spoken so far
        instead of waiting for the silence timeout.
        """
        with self._lock:
            if self.state != "LISTENING":
                return {"status": self.state.lower()}

            self._cancel_silence_timer()

            if self._utterance_buffer:
                # Process the buffer immediately (same as silence timeout)
                threading.Thread(
                    target=self._on_silence_timeout,
                    daemon=True,
                ).start()
                return {"status": "processing"}
            else:
                # Nothing was said — just go idle
                self._set_state("IDLE")
                return {"status": "idle"}

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