"""Message router for the Arcturus omni-channel gateway.

Routes normalized MessageEnvelopes to the appropriate agent instances
based on channel, conversation ID, and session affinity policies.
"""

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from gateway.envelope import MessageEnvelope

if TYPE_CHECKING:
    from gateway.formatter import MessageFormatter

logger = logging.getLogger(__name__)

# Default bot mention token checked when group_activation == "mention-only"
_DEFAULT_BOT_MENTION = "@arcturus"


class MessageRouter:
    """Routes messages to agent instances based on conversation context.

    Implements session affinity: ensures messages from the same conversation
    are routed to the same agent instance for continuity.

    Group activation policies (per channel):
    - ``"always-on"``: every message is routed to the agent (default).
    - ``"mention-only"``: message is only routed when it contains the bot
      mention token (default: ``@arcturus``).  Messages that don't mention
      the bot return ``{"routed": False, "reason": "mention_required"}``.
    """

    def __init__(
        self,
        agent_factory: Callable[..., Any],
        formatter: "MessageFormatter | None" = None,
        group_activation: dict[str, str] | None = None,
        bot_mention: str = _DEFAULT_BOT_MENTION,
    ):
        """Initialize the message router.

        Args:
            agent_factory: Callable that creates or retrieves an agent instance.
            formatter: Optional MessageFormatter for outbound reply formatting.
            group_activation: Per-channel activation policy map, e.g.
                ``{"telegram": "mention-only", "webchat": "always-on"}``.
                Channels not present default to ``"always-on"``.
            bot_mention: Token that counts as a mention in ``mention-only``
                mode (case-insensitive).  Defaults to ``"@arcturus"``.
        """
        self.agent_factory = agent_factory
        self.formatter = formatter
        self.group_activation: dict[str, str] = group_activation or {}
        self.bot_mention = bot_mention.lower()
        self.sessions: dict[str, Any] = {}  # In-memory session map

    def _is_activated(self, envelope: MessageEnvelope) -> bool:
        """Return True if the envelope should be routed to an agent.

        Checks the group_activation policy for the envelope's channel:
        - ``"always-on"`` (or not configured): always True.
        - ``"mention-only"``: True only when bot_mention appears in the
          message content (case-insensitive).
        """
        policy = self.group_activation.get(envelope.channel, "always-on")
        if policy == "mention-only":
            return self.bot_mention in envelope.content.lower()
        return True  # "always-on" or unknown policy

    async def route(self, envelope: MessageEnvelope) -> dict[str, Any]:
        """Route a message envelope to the appropriate agent.

        Args:
            envelope: MessageEnvelope to route

        Returns:
            Dict with routing result, agent response, and metadata
        """
        # Group activation gate — skip agent for mention-only channels with no mention
        if not self._is_activated(envelope):
            logger.info(
                f"Skipping message from {envelope.sender_name} on {envelope.channel} "
                f"(mention-only policy, no '{self.bot_mention}' in message)"
            )
            return {
                "routed": False,
                "session_id": None,
                "channel": envelope.channel,
                "message_id": envelope.channel_message_id,
                "agent_response": None,
                "status": "skipped",
                "reason": "mention_required",
            }

        # Determine session ID for routing
        session_id = envelope.session_id or envelope.conversation_id or envelope.thread_id
        if not session_id:
            # Fallback: create session from channel + sender
            session_id = f"{envelope.channel}_{envelope.sender_id}"

        logger.info(
            f"Routing message from {envelope.sender_name} on {envelope.channel} to session {session_id}"
        )

        # Get or create agent instance for this session
        agent = await self._get_or_create_agent(session_id)
        print(f"[ROUTER] agent type: {type(agent).__name__} for session {session_id}")

        # Process message through agent
        result = await self._process_message(agent, envelope)
        print(f"[ROUTER] _process_message returned: {str(result)[:200]}")

        # NOTE: Do NOT format here — bus.deliver() already applies the formatter.
        # Formatting twice double-escapes MarkdownV2 chars (e.g. "." → "\." → "\\.").

        return {
            "routed": True,
            "session_id": session_id,
            "channel": envelope.channel,
            "message_id": envelope.channel_message_id,
            "agent_response": result,
            "status": "success",
        }

    async def _get_or_create_agent(self, session_id: str) -> Any:
        """Get existing agent or create new one for session.

        Implements session affinity: same session always routes to same agent.

        Args:
            session_id: Unique session identifier

        Returns:
            Agent instance for this session
        """
        if session_id in self.sessions:
            logger.debug(f"Reusing agent for session {session_id}")
            return self.sessions[session_id]

        logger.debug(f"Creating new agent for session {session_id}")
        agent = await self.agent_factory(session_id=session_id)
        self.sessions[session_id] = agent
        return agent

    async def _process_message(self, agent: Any, envelope: MessageEnvelope) -> dict[str, Any]:
        """Process a message through an agent.

        Args:
            agent: Agent instance
            envelope: MessageEnvelope to process

        Returns:
            Agent response dict
        """
        # Call agent's message processing method
        # The agent object should have an async method like process_message()
        # or we can call it as a callable
        if hasattr(agent, "process_message") and callable(agent.process_message):
            response = await agent.process_message(envelope)
        elif callable(agent):
            response = await agent(envelope)
        else:
            # Fallback: return mock response
            response = self._mock_agent_response(envelope)

        return response

    @staticmethod
    def _mock_agent_response(envelope: MessageEnvelope) -> dict[str, Any]:
        """Generate a mock agent response for testing/stub purposes.

        Args:
            envelope: MessageEnvelope that was processed

        Returns:
            Mock agent response dict
        """
        return {
            "status": "processed",
            "message_id": envelope.channel_message_id,
            "reply": f"Echo: {envelope.content}",
            "channel": envelope.channel,
            "sender_id": envelope.sender_id,
        }

    async def shutdown(self) -> None:
        """Gracefully shutdown all agent sessions."""
        logger.info(f"Shutting down {len(self.sessions)} agent sessions")
        # Clean up any resources associated with agents if needed
        self.sessions.clear()


async def create_mock_agent(session_id: str) -> Any:
    """Factory function to create a mock agent for testing.

    Args:
        session_id: Unique session identifier

    Returns:
        Mock agent object with process_message method
    """

    class MockAgent:
        """Simple mock agent for testing."""

        def __init__(self, session_id: str):
            self.session_id = session_id
            self.message_count = 0

        async def process_message(self, envelope: MessageEnvelope) -> dict[str, Any]:
            """Process a message (mock implementation).

            Args:
                envelope: MessageEnvelope to process

            Returns:
                Mock response dict
            """
            self.message_count += 1
            return {
                "status": "processed",
                "message_id": envelope.channel_message_id,
                "reply": f"[Session {self.session_id}] Processed: {envelope.content}",
                "channel": envelope.channel,
                "sender_id": envelope.sender_id,
                "message_number": self.message_count,
            }

    return MockAgent(session_id)


# ---------------------------------------------------------------------------
# Real-agent factory — backed by AgentLoop4 via /api/runs
# ---------------------------------------------------------------------------


async def _fetch_run_output(run_id: str) -> dict:
    """Read run output directly from the session summary on disk."""
    import json as _json

    from shared.state import PROJECT_ROOT

    summaries_dir = PROJECT_ROOT / "memory" / "session_summaries_index"
    for session_file in summaries_dir.rglob(f"session_{run_id}.json"):
        try:
            data = _json.loads(session_file.read_text())
            graph = data.get("graph", {})
            status = graph.get("status", "unknown")
            # nodes live at top-level data["nodes"], not inside "graph"
            nodes = data.get("nodes", [])
            output_text = None
            for node in reversed(nodes):
                # nx.node_link_data() puts attributes directly on node dict
                raw = node.get("output")
                if raw:
                    # Output may be a dict (e.g. {"markdown_report": "..."}) or a string
                    if isinstance(raw, dict):
                        output_text = (
                            raw.get("markdown_report")
                            or raw.get("report")
                            or raw.get("text")
                            or raw.get("content")
                            or str(raw)
                        )
                    else:
                        output_text = str(raw)
                    break
            return {"run_id": run_id, "status": status, "output": output_text}
        except Exception:
            pass
    return {"run_id": run_id, "status": "failed", "output": None}


async def create_runs_agent(session_id: str) -> Any:
    """Factory that creates an agent backed by the real AgentLoop4 (in-process).

    Calls ``routers.runs.process_run`` directly instead of going over HTTP,
    which avoids self-request deadlocks when the gateway runs inside the same
    uvicorn process.

    Known limitation: each call starts a *fresh* AgentLoop4 run — there is no
    cross-message conversation memory.  This is a documented P01 known gap;
    persistent session continuity requires deeper runs-API changes (P15 scope).
    """

    # Maximum conversation turns to keep (user + assistant pairs)
    _MAX_HISTORY_TURNS = 10

    class RunsAgentAdapter:
        """Adapter that delegates to AgentLoop4 via direct in-process call.

        Maintains a rolling conversation history so follow-up questions have
        context from earlier turns.  The history is prepended to the query
        as a ``CONVERSATION HISTORY`` block that the PlannerAgent sees.
        """

        def __init__(self, session_id: str):
            self.session_id = session_id
            self._history: list[dict[str, str]] = []  # [{"role": "user"|"assistant", "content": ...}, ...]

        def _handle_command(self, command: str, envelope: MessageEnvelope) -> dict[str, Any]:
            """Handle slash commands (/start, /help, etc.) without triggering an agent run."""
            cmd = command.split()[0].lower()

            if cmd in ("/start", "/help"):
                welcome = (
                    "Welcome to Arcturus!\n\n"
                    "Available modes:\n"
                    "  /simple — Quick answers (local Gemma, free)\n"
                    "  /complex — Deep research (Gemini cloud)\n"
                    "  /run — Full multi-agent pipeline (RUNS)\n"
                    "  /slides — Create presentations (Forge)\n"
                    "  /schedule — Set up recurring tasks\n"
                    "  /rag — Search knowledge base\n"
                    "  /menu — Show interactive menu\n\n"
                    "Just type your message — it routes to your current mode!"
                )
            elif cmd == "/status":
                welcome = f"Session: {self.session_id}\nHistory: {len(self._history)} messages"
            elif cmd == "/clear":
                self._history.clear()
                welcome = "Conversation history cleared."
            else:
                welcome = f"Unknown command: {cmd}\nType /help to see available options."

            return {
                "status": "completed",
                "reply": welcome,
                "channel": envelope.channel,
                "sender_id": envelope.sender_id,
            }

        @staticmethod
        def _classify_intent(message: str) -> tuple:
            """Classify user intent → (app, skill_id).

            Returns one of:
              ('run', None)      – default agent pipeline
              ('forge', None)    – create slides / document / sheet via Studio
              ('schedule', None) – create a scheduled job
            """
            lower = message.lower()

            forge_triggers = [
                "create slides", "create presentation", "make a presentation",
                "pitch deck", "create document", "make slides", "generate slides",
                "build a deck", "make a deck",
            ]
            if any(t in lower for t in forge_triggers):
                return ("forge", None)

            schedule_triggers = [
                "remind me", "every day", "every week", "schedule",
                "every morning", "daily at", "weekly", "every hour",
            ]
            if any(t in lower for t in schedule_triggers):
                return ("schedule", None)

            return ("run", None)

        @staticmethod
        def _parse_schedule(message: str) -> tuple[str, str]:
            """Parse natural language schedule into (cron_expression, task_query).

            Simple keyword-based parser — no LLM call needed.
            """
            import re
            lower = message.lower()

            # Strip schedule-related preamble to get the actual task
            task = re.sub(
                r"(remind me|schedule|set up|create a reminder)(\s+to)?\s*",
                "", message, count=1, flags=re.IGNORECASE,
            ).strip()
            # Remove time phrases from the task description
            task = re.sub(
                r"\b(every\s+(morning|evening|day|week|hour|monday|tuesday|wednesday|"
                r"thursday|friday|saturday|sunday)|daily\s+at\s+\S+|weekly|hourly)\b",
                "", task, flags=re.IGNORECASE,
            ).strip().strip(",").strip()
            if not task:
                task = message  # fallback to original

            # Parse time expression → cron
            if "every hour" in lower or "hourly" in lower:
                return ("0 * * * *", task)
            if "every morning" in lower:
                return ("0 9 * * *", task)
            if "every evening" in lower:
                return ("0 18 * * *", task)
            if "every monday" in lower:
                return ("0 9 * * 1", task)
            if "every tuesday" in lower:
                return ("0 9 * * 2", task)
            if "every wednesday" in lower:
                return ("0 9 * * 3", task)
            if "every thursday" in lower:
                return ("0 9 * * 4", task)
            if "every friday" in lower:
                return ("0 9 * * 5", task)
            if "every saturday" in lower:
                return ("0 9 * * 6", task)
            if "every sunday" in lower:
                return ("0 9 * * 0", task)
            if "every week" in lower or "weekly" in lower:
                return ("0 9 * * 1", task)

            # "daily at HH:MM" or "daily at Ham/Hpm"
            m = re.search(r"daily\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", lower)
            if m:
                hour = int(m.group(1))
                minute = int(m.group(2) or 0)
                ampm = m.group(3)
                if ampm == "pm" and hour < 12:
                    hour += 12
                elif ampm == "am" and hour == 12:
                    hour = 0
                return (f"{minute} {hour} * * *", task)

            # Default: every day at 9 AM
            if "every day" in lower or "daily" in lower:
                return ("0 9 * * *", task)

            # Fallback
            return ("0 9 * * *", task)

        async def _handle_simple_query(self, envelope: MessageEnvelope) -> dict[str, Any]:
            """Handle a simple query using local Gemma model (free, fast, no agent pipeline)."""
            try:
                from core.model_manager import ModelManager

                print(f"[SIMPLE] Using Gemma 3 12B (local Ollama) for: {envelope.content[:80]}")
                mm = ModelManager(model_name="gemma3:12b", provider="ollama")
                prompt = self._build_contextual_query(envelope.content)
                result = await mm.generate_text(prompt)
                print(f"[SIMPLE] Gemma response ({len(result)} chars): {result[:120]}")

                self._history.append({"role": "assistant", "content": result[:500]})
                self._trim_history()

                return {
                    "status": "completed",
                    "reply": result,
                    "channel": envelope.channel,
                    "sender_id": envelope.sender_id,
                }
            except Exception as exc:
                logger.error("Simple query failed: %s", exc, exc_info=True)
                return {
                    "status": "error",
                    "reply": f"Local model unavailable: {exc}\nTry /complex for cloud-based AI.",
                    "channel": envelope.channel,
                    "sender_id": envelope.sender_id,
                }

        async def _handle_rag_query(self, envelope: MessageEnvelope) -> dict[str, Any]:
            """Handle a RAG keyword search directly on metadata.json (no embeddings needed)."""
            import json as _json
            from pathlib import Path as _P

            print(f"[RAG] Keyword search for: {envelope.content[:80]}")

            meta_path = _P(__file__).resolve().parent.parent / "mcp_servers" / "faiss_index" / "metadata.json"
            if not meta_path.exists():
                print(f"[RAG] metadata.json not found at {meta_path}")
                return {
                    "status": "completed",
                    "reply": "No documents indexed yet. Upload and index documents via the web UI RAG tab first.",
                    "channel": envelope.channel,
                    "sender_id": envelope.sender_id,
                }

            try:
                metadata = _json.loads(meta_path.read_text())

                # Split query into keywords for multi-word matching
                keywords = [w.lower() for w in envelope.content.split() if len(w) >= 2]
                if not keywords:
                    keywords = [envelope.content.lower()]

                # Score each chunk by keyword hits; skip conversation_history/session logs
                scored: list[tuple[int, str]] = []
                for entry in metadata:
                    doc = entry.get("doc", "")
                    # Filter out session logs / conversation history
                    if "conversation_history" in doc or doc.startswith("session_"):
                        continue
                    chunk_text = entry.get("chunk", "").strip()
                    if not chunk_text:
                        continue
                    chunk_lower = chunk_text.lower()
                    hits = sum(1 for kw in keywords if kw in chunk_lower)
                    if hits > 0:
                        page = entry.get("page", 1)
                        scored.append((hits, f"{chunk_text}\n[Source: {doc} p{page}]"))

                # Sort by relevance (most keyword hits first), take top 5
                scored.sort(key=lambda x: x[0], reverse=True)
                results = [text for _, text in scored[:5]]

                if not results:
                    reply = f"No matches found for '{envelope.content}' in the knowledge base."
                else:
                    reply = f"Found {len(results)} result(s):\n\n"
                    for i, r in enumerate(results, 1):
                        text = r[:600] if len(r) > 600 else r
                        reply += f"--- Result {i} ---\n{text}\n\n"

                print(f"[RAG] Found {len(results)} matches")
                self._history.append({"role": "assistant", "content": reply[:500]})
                self._trim_history()

                return {
                    "status": "completed",
                    "reply": reply,
                    "channel": envelope.channel,
                    "sender_id": envelope.sender_id,
                }
            except Exception as exc:
                logger.error("RAG keyword search failed: %s", exc, exc_info=True)
                print(f"[RAG] Error: {exc}")
                return {
                    "status": "error",
                    "reply": f"RAG search failed: {exc}",
                    "channel": envelope.channel,
                    "sender_id": envelope.sender_id,
                }

        def _build_contextual_query(self, current_message: str) -> str:
            """Prepend conversation history to the current message."""
            if not self._history:
                return current_message

            lines = ["CONVERSATION HISTORY (most recent messages):"]
            for turn in self._history:
                role = turn["role"].upper()
                lines.append(f"  {role}: {turn['content']}")
            lines.append("")
            lines.append(f"CURRENT USER MESSAGE: {current_message}")
            lines.append("")
            lines.append("Answer the CURRENT USER MESSAGE. Use the conversation history for context if the user refers to previous topics.")
            return "\n".join(lines)

        def _trim_history(self):
            """Keep only the last N turns to avoid unbounded growth."""
            max_items = _MAX_HISTORY_TURNS * 2  # user + assistant per turn
            if len(self._history) > max_items:
                self._history = self._history[-max_items:]

        async def process_message(self, envelope: MessageEnvelope) -> dict[str, Any]:
            from datetime import datetime as _dt

            from routers.runs import process_run

            content_stripped = envelope.content.strip()

            # Determine routing mode FIRST:
            # 1. Explicit mode from Telegram menu/buttons (envelope.mode)
            # 2. Fallback to keyword classification (for web UI which has no mode)
            mode = envelope.mode

            # Handle bot commands — but ONLY if no explicit mode is set.
            # When mode is set (e.g. "simple"), the text is a clean query, not a command.
            if not mode and content_stripped.startswith("/"):
                return self._handle_command(content_stripped, envelope)

            if not mode:
                app, _skill = self._classify_intent(envelope.content)
                mode = app  # "run", "forge", "schedule"

            run_id = f"nexus_{int(_dt.now().timestamp())}"
            contextual_query = self._build_contextual_query(envelope.content)
            print(f"\n{'='*60}")
            print("[NEXUS] create_runs_agent.process_message called")
            print(f"[NEXUS]   run_id   = {run_id}")
            print(f"[NEXUS]   channel  = {envelope.channel}")
            print(f"[NEXUS]   sender   = {envelope.sender_id}")
            print(f"[NEXUS]   content  = {envelope.content[:80]}")
            print(f"[NEXUS]   mode     = {mode}")
            print(f"[NEXUS]   history  = {len(self._history)} turns")
            print(f"{'='*60}")
            logger.info(
                "create_runs_agent: starting run %s for '%s' (mode=%s)",
                run_id, envelope.content[:60], mode,
            )

            # Record the user turn before processing
            self._history.append({"role": "user", "content": envelope.content})

            print(f"[NEXUS]   mode     = {mode}")

            # --- Simple Query: direct Gemma call, no agent pipeline ---
            if mode == "simple":
                return await self._handle_simple_query(envelope)

            # --- RAG: knowledge base search ---
            if mode == "rag":
                return await self._handle_rag_query(envelope)

            # --- Forge / Slides ---
            if mode in ("forge", "slides"):
                try:
                    from core.studio.orchestrator import ForgeOrchestrator
                    from core.studio.storage import get_studio_storage
                    orch = ForgeOrchestrator(get_studio_storage())
                    result = await orch.generate_outline(
                        prompt=envelope.content,
                        artifact_type="slides",
                    )
                    artifact_id = result.get("artifact_id", "")
                    print(f"[SLIDES] Outline created: artifact_id={artifact_id}")

                    # Export to PDF so Telegram can receive the file
                    pdf_path = None
                    try:
                        from core.schemas.studio_schema import ExportFormat
                        export_result = await orch.export_artifact(
                            artifact_id=artifact_id,
                            export_format=ExportFormat.pdf,
                        )
                        export_job_id = export_result.get("id", "")
                        # PDF export runs async — poll until done (max ~60s)
                        import asyncio as _aio
                        storage = get_studio_storage()
                        job = None
                        for _ in range(30):
                            await _aio.sleep(2)
                            job = storage.load_export_job(artifact_id, export_job_id)
                            if job and job.status.value in ("completed", "failed"):
                                break
                        if job and job.status.value == "completed" and job.output_uri:
                            pdf_path = job.output_uri
                            print(f"[SLIDES] PDF exported: {pdf_path}")
                    except Exception as pdf_exc:
                        logger.warning("PDF export failed (outline still created): %s", pdf_exc)
                        print(f"[SLIDES] PDF export failed: {pdf_exc}")

                    if pdf_path:
                        reply = f"Presentation created! Sending PDF..."
                    else:
                        reply = f"Presentation outline created! Open Forge in the web UI to export.\nArtifact ID: {artifact_id}"

                    self._history.append({"role": "assistant", "content": reply})
                    self._trim_history()
                    response = {
                        "status": "completed",
                        "reply": reply,
                        "channel": envelope.channel,
                        "sender_id": envelope.sender_id,
                        "run_id": f"forge_{artifact_id}",
                    }
                    if pdf_path:
                        response["file_path"] = pdf_path
                        response["file_caption"] = f"Presentation: {envelope.content[:100]}"
                    return response
                except Exception as exc:
                    logger.error("Forge routing failed: %s", exc, exc_info=True)
                    mode = "runs"  # Fall through to full pipeline

            # --- Schedule ---
            if mode == "schedule":
                try:
                    cron_expr, task_query = self._parse_schedule(envelope.content)
                    from core.scheduler import SchedulerService
                    svc = SchedulerService()
                    if not svc.initialized:
                        svc.initialize()
                    job = svc.add_job(
                        name=task_query[:80],
                        cron_expression=cron_expr,
                        agent_type="default",
                        query=task_query,
                        timezone="Asia/Kolkata",
                    )
                    next_run = job.next_run or "soon"
                    reply = (
                        f"Scheduled!\n\n"
                        f"Job: {task_query}\n"
                        f"Schedule: {cron_expr}\n"
                        f"Next run: {next_run}\n\n"
                        f"View and manage jobs in the Scheduler tab."
                    )
                    self._history.append({"role": "assistant", "content": reply})
                    self._trim_history()
                    return {
                        "status": "completed",
                        "reply": reply,
                        "channel": envelope.channel,
                        "sender_id": envelope.sender_id,
                    }
                except Exception as exc:
                    logger.error("Schedule routing failed: %s", exc, exc_info=True)
                    mode = "runs"  # Fall through to full pipeline

            # --- Complex / RUNS: full multi-agent pipeline ---

            try:
                run_result = await process_run(
                    run_id, contextual_query,
                    display_query=envelope.content,
                    source=envelope.channel,
                )
                print(f"[NEXUS] process_run({run_id}) completed successfully")
            except Exception as exc:
                print(f"[NEXUS] process_run({run_id}) RAISED: {exc}")
                logger.error("create_runs_agent: process_run raised: %s", exc, exc_info=True)
                self._history.append({"role": "assistant", "content": "(error)"})
                self._trim_history()
                return {
                    "status": "error",
                    "reply": "The agent encountered an error. Please try again.",
                    "channel": envelope.channel,
                    "sender_id": envelope.sender_id,
                }

            # 1. Try to get output directly from process_run return value
            output_text = ""
            if isinstance(run_result, dict):
                raw = run_result.get("output", "") or ""
                # Reject raw Python code fragments / bare JSON blobs leaked from intermediate nodes
                _code_signals = ("return {", "json.loads(", "import ", "def ", "results =")
                _stripped = raw.lstrip()
                _is_code_fragment = any(_stripped.startswith(s) for s in _code_signals)
                # Also reject bare dict/list blobs (start with { or [ and contain Python-ish keys)
                _is_raw_json = (
                    (_stripped.startswith("{") or _stripped.startswith("["))
                    and ("':" in _stripped or '":' in _stripped or "'," in _stripped)
                )
                if raw and not _is_code_fragment and not _is_raw_json:
                    output_text = raw
                print(f"[NEXUS] process_run returned output ({len(output_text)} chars)")

            # 2. Fall back to disk if process_run didn't return output
            if not output_text:
                result = await _fetch_run_output(run_id)
                output_text = result.get("output", "") or ""
                print(f"[NEXUS] _fetch_run_output({run_id}) = output_len={len(output_text)}")

            if not output_text:
                print(f"[NEXUS] WARNING: No output found for {run_id}!")
                self._history.append({"role": "assistant", "content": "(no output)"})
                self._trim_history()
                return {
                    "status": "failed",
                    "reply": "The agent could not complete your request. Please try again.",
                    "channel": envelope.channel,
                    "sender_id": envelope.sender_id,
                }

            reply = output_text
            # Truncate stored history to avoid bloating future prompts
            self._history.append({"role": "assistant", "content": reply[:500]})
            self._trim_history()

            return {
                "status": "completed",
                "reply": reply,
                "channel": envelope.channel,
                "sender_id": envelope.sender_id,
                "run_id": run_id,
            }

    return RunsAgentAdapter(session_id)
