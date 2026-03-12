# voice/intent_gate.py
"""
Intent Gating Layer — real-time utterance classification for voice pipelines.

Decides—before any pipeline runs—whether a completed utterance should:
  DICTATION  – write exactly what the user said, zero inference
  COMMAND    – deterministic skill / UI navigation, no LLM planning
  AGENTIC    – multi-step reasoning, tools, memory

Safety guarantee
----------------
Agentic is NEVER the default.  It must be explicitly earned by strong
signal words AND a confidence ≥ AGENTIC_CONFIDENCE_THRESHOLD.
When uncertain the gate either downgrades or asks a minimal clarification.

Design constraints
------------------
• Streaming-friendly: `classify_partial()` runs on partial transcripts to
  give early routing hints while STT is still speaking.
• <150 ms per decision (pure Python regex + lightweight LLM call).
• Barge-in compatible: all classification paths are interruptible.
• No mutable global state — thread-safe by construction.
"""

from __future__ import annotations

import re
import time
import enum
import threading
import json
import asyncio
from dataclasses import dataclass, field
from typing import Optional

from core.model_manager import ModelManager
from voice.config import VOICE_CONFIG

# ─────────────────────────────────────────────────────────────────────────────
# 1.  Intent Enum (non-negotiable)
# ─────────────────────────────────────────────────────────────────────────────

class IntentType(str, enum.Enum):
    DICTATION = "DICTATION"   # write exactly what user says, no inference
    COMMAND   = "COMMAND"     # deterministic UI / skill execution
    AGENTIC   = "AGENTIC"     # multi-step reasoning, tools, memory


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Gate Decision (output contract)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class GateDecision:
    intent_type:           IntentType
    confidence:            float          # 0.0 – 1.0
    should_escalate:       bool           # True → route to next tier
    requires_clarification:bool           # True → ask user before acting
    interruptible:         bool           # True → barge-in cancels this path
    clarification_prompt:  Optional[str] = None   # set when requires_clarification
    latency_ms:            float          = 0.0
    reasoning:             str            = ""

    def to_dict(self) -> dict:
        return {
            "intent_type":            self.intent_type.value,
            "confidence":             round(self.confidence, 3),
            "should_escalate":        self.should_escalate,
            "requires_clarification": self.requires_clarification,
            "interruptible":          self.interruptible,
            "clarification_prompt":   self.clarification_prompt,
            "latency_ms":             round(self.latency_ms, 1),
            "reasoning":              self.reasoning,
        }


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Configuration + Known Skills Registry
# ─────────────────────────────────────────────────────────────────────────────

# Minimum confidence required before AGENTIC is allowed to run.
# NEVER lower this below 0.75 without explicit justification.
AGENTIC_CONFIDENCE_THRESHOLD = 0.80

# Required confidence for any decision — below this we clarify.
CLARIFICATION_THRESHOLD = 0.60

# Known command verbs and skill mappings — deterministic, no LLM needed.
_COMMAND_VERBS = {
    "open", "go", "navigate", "show", "hide", "close", "launch", "switch",
    "play", "pause", "stop", "mute", "unmute", "volume", "display",
    "fetch", "load", "refresh", "search", "find", "scroll",
    "create", "add", "delete", "remove", "set", "enable", "disable",
}



# ── Navigation keyword → tab name mapping ─────────────────────────────────────
# Keys are lowercased keywords; the first match wins.
_NAVIGATION_ROUTES: list[tuple[str, str]] = [
    ("dashboard",    "runs"),
    ("runs",         "runs"),
    ("notes",        "notes"),
    ("note",         "notes"),
    ("rag",          "rag"),
    ("knowledge",    "rag"),
    ("settings",     "settings"),
    ("apps",         "apps"),
    ("explorer",     "explorer"),
    ("scheduler",    "scheduler"),
    ("ide",          "ide"),
    ("console",      "console"),
    ("studio",       "studio"),
    ("skills",       "skills"),
    ("canvas",       "canvas"),
    ("mcp",          "mcp"),
    ("remme",        "remme"),
    ("memory",       "remme"),
    ("vault",        "remme"),
    ("news",         "news"),
    ("search",       "news"),
    ("learn",        "learn"),
    ("echo",         "echo"),
    ("voice",        "echo"),
    ("apps",         "apps"),
    ("builder",      "apps"),
    ("inbox",        "inbox"),
    ("calendar",     "calendar"),
    ("home",         "runs"),
]

# Dictation frame phrases — strong signals that user wants transcription only.
_DICTATION_FRAMES = [
    r"\bwrite\b.*\bsay(ing)?\b",
    r"\b(meeting notes?|notes?)\s*[:,]",
    r"\bdictate\b",
    r"\btranscribe\b",
    r"\btype\b.*\b(for me|this)\b",
    r"\brecord\b.*\bwhat\b.*\bsay\b",
    r"\bword for word\b",
    r"\bjust write\b",
    r"\bwrite (down|this|it)\b",
]

# Agentic signal patterns — multi-step, delegation, planning language.
_AGENTIC_SIGNALS = [
    r"\bcheck\b.*\band\b.*\b(summar|tell|report|let me know)\b",
    r"\bfigure out\b",
    r"\binvestigate\b",
    r"\bfind (out|and)\b.*\b(fix|resolve|handle)\b",
    r"\b(plan|organiz|schedul)\b.*\b(for me|everything|all)\b",
    r"\bautomatically\b",
    r"\bgo (ahead|through)\b.*\band\b",
    r"\b(handle|take care of|deal with)\b.*\bfor me\b",
    r"\bdo (whatever|everything|anything)\b",
    r"\bstep by step\b.*\b(fix|solve|address)\b",
    r"\bset up\b.*\band\b.*\bthen\b",
    r"\bwhile (you're at it|you're doing)\b",
]

# Query signals — question forms, single-step.
_QUERY_SIGNALS = [
    r"^(what|how|why|when|where|who|which|whose|whom|is|are|was|were|can|could|do|does|did)\b",
    r"\?$",
    r"\bexplain\b",
    r"\btell me (about|what)\b",
    r"\bdefine\b",
    r"\bwhat (is|are|does)\b",
    r"\bhow (does|do|can|to)\b",
]


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Rule-Based Classifier (fast path — <5ms)
# ─────────────────────────────────────────────────────────────────────────────

def _score_dictation(text: str) -> float:
    """Return a dictation confidence score 0.0–1.0."""
    t = text.lower().strip()
    score = 0.0
    for pattern in _DICTATION_FRAMES:
        if re.search(pattern, t):
            score += 0.35
    # No imperative verb at the start → mild dictation signal
    first_word = t.split()[0] if t.split() else ""
    if first_word not in _COMMAND_VERBS and not re.search(r'^(what|how|why|when|can)\b', t):
        score += 0.10
    # Long utterance with no action words → dictation-like
    if len(t.split()) > 15 and not any(re.search(p, t) for p in _AGENTIC_SIGNALS):
        score += 0.15
    return min(score, 1.0)


def _score_command(text: str) -> float:
    """Return a command confidence score 0.0–1.0."""
    t = text.lower().strip()
    words = t.split()
    score = 0.0
    # Starts with a known command verb
    if words and words[0] in _COMMAND_VERBS:
        score += 0.45
    # Maps to a known skill — but only if the utterance is short (command-like).
    # Long utterances with multi-step language are likely AGENTIC even if they
    # mention a skill keyword (e.g. "check my emails and summarize anything").
    has_agentic = any(re.search(p, t) for p in _AGENTIC_SIGNALS)
    if not has_agentic and len(words) <= 10:
        for keyword, _ in _NAVIGATION_ROUTES:
            if keyword in t:
                score += 0.30
                break
    # Short utterance (≤6 words) with verb → high command likelihood
    if len(words) <= 6 and score > 0:
        score += 0.15
    return min(score, 1.0)


def _score_query(text: str) -> float:
    """Return a query confidence score 0.0–1.0."""
    t = text.lower().strip()
    score = 0.0
    for pattern in _QUERY_SIGNALS:
        if re.search(pattern, t):
            score += 0.30
    # No agentic or dictation signals
    if not any(re.search(p, t) for p in _AGENTIC_SIGNALS):
        score += 0.10
    if not any(re.search(p, t) for p in _DICTATION_FRAMES):
        score += 0.05
    return min(score, 1.0)


def _score_agentic(text: str) -> float:
    """
    Return an agentic confidence score 0.0–1.0.
    ⚠️  This score must reach AGENTIC_CONFIDENCE_THRESHOLD before routing
    to the agentic pipeline.  Low scores stay as QUERY.
    """
    t = text.lower().strip()
    score = 0.0
    for pattern in _AGENTIC_SIGNALS:
        if re.search(pattern, t):
            score += 0.35
    # Multi-clause sentence → planning implied
    clause_count = len(re.findall(r'\b(and then|after that|then|also|additionally|furthermore)\b', t))
    score += clause_count * 0.12
    # Long imperative sentence with tools implied
    if len(t.split()) > 10 and re.search(r'\b(email|calendar|file|code|repo|build|test)\b', t):
        score += 0.10
    return min(score, 1.0)


# ─────────────────────────────────────────────────────────────────────────────
# 5.  Gate Decision Function
# ─────────────────────────────────────────────────────────────────────────────

def classify(text: str) -> GateDecision:
    """
    Classify a complete utterance and return a GateDecision.

    This is the PRIMARY entry point.  Call after STT silence timeout.
    Thread-safe, no side effects.

    Clarification is intentionally disabled: the gate always dispatches
    immediately without asking the user for clarification.  Mid-run
    clarification is handled by the Nexus ClarificationAgent instead.
    """
    t0 = time.perf_counter()
    text = text.strip()

    if not text:
        return GateDecision(
            intent_type=IntentType.AGENTIC,
            confidence=0.0,
            should_escalate=False,
            requires_clarification=False,
            interruptible=True,
            reasoning="empty utterance — routed as low-confidence query",
        )

    # Score all four intents
    scores = {
        IntentType.DICTATION: _score_dictation(text),
        IntentType.COMMAND:   _score_command(text),
        IntentType.AGENTIC:   _score_agentic(text),
    }

    best_intent = max(scores, key=scores.__getitem__)
    best_score  = scores[best_intent]

    # ── Safety gate: AGENTIC is never auto-selected below threshold ──────────
    if best_intent == IntentType.AGENTIC:
        reasoning = f"Agentic confirmed: score={best_score:.2f}"
    elif best_intent == IntentType.DICTATION:
        reasoning = f"Dictation detected: score={best_score:.2f}"
    elif best_intent == IntentType.COMMAND:
        reasoning = f"Command detected: score={best_score:.2f}"
    else:
        reasoning = f"Agentic: score={best_score:.2f}"

    latency_ms = (time.perf_counter() - t0) * 1000

    return GateDecision(
        intent_type=best_intent,
        confidence=round(best_score, 3),
        should_escalate=(best_intent == IntentType.AGENTIC),
        requires_clarification=False,
        interruptible=(best_intent != IntentType.DICTATION),
        latency_ms=latency_ms,
        reasoning=reasoning,
    )


def classify_partial(partial_text: str) -> Optional[IntentType]:
    """
    Early-hint classifier for partial STT transcripts (streaming mode).

    Returns None if insufficient signal, or an IntentType hint so the
    orchestrator can warm-start the right pipeline before STT finishes.

    Only high-confidence, early signals are returned — never AGENTIC
    (we never pre-warm the agentic pipeline from a partial transcript).
    """
    if len(partial_text.split()) < 2:
        return None

    t = partial_text.lower().strip()
    first_word = t.split()[0]

    # Strong early COMMAND signal: known verb at start
    if first_word in _COMMAND_VERBS and len(t.split()) >= 2:
        return IntentType.COMMAND

    # Strong early DICTATION signal — check all registered frames
    for pattern in _DICTATION_FRAMES:
        if re.search(pattern, t):
            return IntentType.DICTATION

    # Early QUERY signal: question word at start → AGENTIC (QUERY was never added to IntentType)
    if re.search(r'^(what|how|why|when|who|where|is|are|can)\b', t):
        return IntentType.AGENTIC

    # Never pre-warm AGENTIC from partial — too risky
    return None





# ─────────────────────────────────────────────────────────────────────────────
# 6.  Router — maps GateDecision → orchestrator action
# ─────────────────────────────────────────────────────────────────────────────

class IntentRouter:
    """
    Stateless router: given a GateDecision, calls the right orchestrator method.
    Inject this into the Orchestrator to replace the hardwired Nexus dispatch.

    Clarification is intentionally removed from this layer.  The intent gate
    always dispatches immediately; mid-run clarification is handled by the
    Nexus ClarificationAgent (voice/orchestrator.py handles the TTS+STT loop).

    Usage:
        router = IntentRouter(orchestrator)
        router.route(utterance)
    """

    def __init__(self, orchestrator):
        self._orch = orchestrator
        self.config = VOICE_CONFIG.get("intent_gate", {})
        self.model_manager = None
        if self.config.get("use_llm"):
            model_name = self.config.get("model")
            self.model_manager = ModelManager(model_name=model_name)

    async def _classify_llm(self, utterance: str) -> Optional[tuple[IntentType, float, str]]:
        """
        Use LLM to classify the intent into COMMAND, DICTATION, or AGENTIC.
        Returns (IntentType, confidence, reasoning) or None if it fails.
        """
        if not self.model_manager:
            return None

        prompt = f"""
You are the **Intent Gate** for Arcturus, a voice assistant.

Your job is to classify the user's utterance into EXACTLY ONE of these intents.

INTENTS
-------

1. DICTATION
User wants to record text exactly as spoken.

Characteristics:
- user wants transcription only
- no action should be executed
- words must be recorded verbatim

Examples:
"start dictation"
"write this down"
"take a note"
"meeting notes colon we discussed roadmap"
"record what I say"
"dictate this"

---

2. COMMAND
User wants a **direct deterministic action** or UI navigation.

Characteristics:
- usually short
- often begins with a verb
- requires immediate action
- no reasoning required

Examples:
"open notes"
"take me to RemMe"
"go to explorer"
"show my settings"
"open dashboard"
"navigate to calendar"
"play music"
"set a timer"

---

3. AGENTIC
Everything else requiring reasoning, knowledge, tools, or analysis.

Characteristics:
- questions
- explanations
- summarization
- research
- multi-step tasks

Examples:
"how is the weather today"
"explain transformers architecture"
"find the bug in api.py"
"summarize my emails"
"check my calendar and tell me what meetings I have"
"investigate why the build failed"

---

DECISION RULES
--------------

1. If the user wants **text written exactly**, choose DICTATION.
2. If the user wants **navigation or a simple action**, choose COMMAND.
3. If the user asks a **question or complex request**, choose AGENTIC.
4. When uncertain between COMMAND and AGENTIC:
   - choose COMMAND if it is a direct UI action
   - otherwise choose AGENTIC.

SAFETY RULE
-----------
AGENTIC should only be selected when reasoning or analysis is clearly required.

---

User Utterance:
"{utterance}"

---

Return ONLY valid JSON in this format:

{{
  "intent": "DICTATION | COMMAND | AGENTIC",
  "confidence": 0.0-1.0,
  "reasoning": "short explanation"
}}

Example:
User: open dashboard
Intent: COMMAND

User: take a note
Intent: DICTATION

User: explain transformers
Intent: AGENTIC
"""

        try:
            response_text = await self.model_manager.generate_text(prompt)
            # Basic cleanup of markdown markers
            clean_json = response_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_json)
            
            intent_str = data.get("intent", "AGENTIC").upper()
            confidence = float(data.get("confidence", 0.5))
            reasoning = data.get("reasoning", "LLM classification")

            # Map to IntentType
            if intent_str == "DICTATION":
                return IntentType.DICTATION, confidence, reasoning
            elif intent_str == "COMMAND":
                return IntentType.COMMAND, confidence, reasoning
            else:
                return IntentType.AGENTIC, confidence, reasoning
        except Exception as e:
            print(f"⚠️ [IntentGate] LLM classification failed: {e}")
            return None

    def route(self, utterance: str) -> GateDecision:
        """
        Classify utterance and route to the correct pipeline.
        Returns the GateDecision for logging / UI feedback.
        """
        # 1. Try LLM classification if enabled
        decision = None
        if self.model_manager:
            try:
                # Use the orchestrator's injected event loop to avoid AnyIO task/scope errors.
                # creating a NEW loop via asyncio.run in a thread is hazardous for MCP/shared async resources.
                loop = self._orch._event_loop
                
                if loop and loop.is_running():
                    try:
                        future = asyncio.run_coroutine_threadsafe(
                            self._classify_llm(utterance), loop
                        )
                        llm_result = future.result(timeout=10.0)
                    except Exception as e:
                        print(f"⚠️ [IntentGate] LLM classification timed out or failed: {e}")
                        llm_result = None
                else:
                    # No loop available (or startup phase) — fallback to rules
                    llm_result = None

                if llm_result:
                    intent, conf, reason = llm_result
                    decision = GateDecision(
                        intent_type=intent,
                        confidence=conf,
                        should_escalate=(intent == IntentType.AGENTIC),
                        requires_clarification=False,
                        interruptible=(intent != IntentType.DICTATION),
                        reasoning=f"LLM: {reason}"
                    )
            except Exception as e:
                print(f"⚠️ [IntentGate] LLM classification block error: {e}")

        # 2. Fallback to rules if LLM disabled or failed
        if not decision:
            decision = classify(utterance)

        print(
            f"🧭 [IntentGate] \"{utterance[:60]}\" → "
            f"{decision.intent_type.value} "
            f"(conf={decision.confidence:.2f})"
        )

        self._dispatch(utterance, decision)
        return decision

    def _dispatch(self, utterance: str, decision: GateDecision) -> None:
        """Route to the correct pipeline based on intent type."""
        intent = decision.intent_type

        if intent == IntentType.DICTATION:
            # ── SAFE PATH: accumulate text, never execute ────────────────────
            # Start a dictation session if not already in one.
            with self._orch._lock:
                already_dictating = (self._orch.state == "DICTATING")
            if not already_dictating:
                self._orch.start_dictation()
            # Re-push the utterance to the active session
            if self._orch._dictation_session:
                self._orch._dictation_session.push_fragment(utterance)

        elif intent == IntentType.COMMAND:
            # ── DETERMINISTIC PATH: only UI navigation ───────────────────────
            # Check if this command maps to a known navigation route.
            has_nav = False
            t_lower = utterance.lower()
            for keyword, _ in _NAVIGATION_ROUTES:
                if keyword in t_lower:
                    has_nav = True
                    break

            if has_nav:
                print(f"🗺️ [IntentGate] Navigation command detected — bypassing Nexus.")
                threading.Thread(
                    target=self._execute_navigation,
                    args=(utterance,),
                    daemon=True,
                ).start()
            else:
                # Not a known navigation route — let Nexus handle it as a general query
                print("⚡ [IntentGate] Command → not navigation, falling back to Nexus.")
                self._route_to_nexus(utterance)

        # IntentType.QUERY does not exist — AGENTIC handles all Q&A via Nexus

        elif intent == IntentType.AGENTIC:
            # ── AGENTIC PATH: only reachable with confidence ≥ threshold ─────
            print(f"🤖 [IntentGate] Agentic escalation approved "
                  f"(conf={decision.confidence:.2f})")
            self._route_to_nexus(utterance)

    def _execute_navigation(self, utterance: str) -> None:
        """
        Instant navigation: resolve the target tab from the utterance,
        publish a ``navigation`` event directly on the event_bus, speak
        confirmation via TTS, and enter the follow-up listening window.

        Zero Nexus calls — completes in < 100 ms.
        """
        t = utterance.lower()
        tab = "runs"  # sensible default
        for keyword, dest in _NAVIGATION_ROUTES:
            if keyword in t:
                tab = dest
                break

        print(f"🗺️ [IntentGate] Navigating to tab: '{tab}' (utterance: '{utterance[:60]}')")

        # Publish navigation event via the orchestrator's safe publish helper
        try:
            self._orch._publish("navigation", {"tab": tab})
        except Exception as e:
            print(f"⚠️ [IntentGate] Navigation event publish failed: {e}")

        # Speak confirmation and enter follow-up listening window.
        spoken = f"Opening {tab}."
        with self._orch._lock:
            self._orch._set_state("SPEAKING")
        self._orch._speak(spoken, source="navigation")
        self._orch._enter_follow_up()

    def _route_to_nexus(self, utterance: str) -> None:
        """Dispatch to the appropriate TTS/Nexus path."""
        use_streaming = self._orch._should_use_streaming()
        if use_streaming:
            threading.Thread(
                target=self._orch._nexus_then_speak_streamed,
                args=(utterance,),
                daemon=True,
            ).start()
        else:
            threading.Thread(
                target=self._orch._nexus_then_speak,
                args=(utterance,),
                daemon=True,
            ).start()



