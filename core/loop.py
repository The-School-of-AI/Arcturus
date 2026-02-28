# flow.py – 100% NetworkX Graph-First (No agentSession)

import networkx as nx
import asyncio
import time
from memory.context import ExecutionContextManager
from ops.tracing import (
    agent_loop_run_span,
    agent_plan_span,
    agent_execute_dag_span,
    agent_execute_node_span,
    agent_iteration_span,
    attach_plan_graph_to_span,
)
from opentelemetry.trace import Status, StatusCode
from agents.base_agent import AgentRunner
from core.utils import log_step, log_error
from core.event_bus import event_bus
from core.model_manager import ModelManager
from ui.visualizer import ExecutionVisualizer
from rich.live import Live
from rich.console import Console
from datetime import datetime


# ===== EXPONENTIAL BACKOFF FOR TRANSIENT FAILURES =====

async def retry_with_backoff(
    async_func,
    max_retries: int = 3,
    base_delay: float = 1.0,
    retryable_errors: tuple = None,
    on_retry=None,
):
    """
    Retry an async function with exponential backoff.

    Args:
        async_func: Async callable to execute
        max_retries: Maximum retry attempts (default: 3)
        base_delay: Initial delay in seconds (default: 1.0)
        retryable_errors: Tuple of exception types to retry on
        on_retry: Optional callback(attempt: int) called before each retry (1-based)

    Returns:
        Result of async_func on success

    Raises:
        Last exception if all retries exhausted
    """
    if retryable_errors is None:
        retryable_errors = (
            asyncio.TimeoutError,
            ConnectionError,
            TimeoutError,
        )

    last_exception = None

    for attempt in range(max_retries):
        try:
            return await async_func()
        except retryable_errors as e:
            last_exception = e
            if attempt < max_retries - 1:
                if on_retry:
                    on_retry(attempt + 1)  # 1-based: first retry = 1
                delay = base_delay * (2 ** attempt)  # 1s, 2s, 4s
                log_step(f"Transient error: {type(e).__name__}. Retrying in {delay}s (attempt {attempt + 1}/{max_retries})", symbol="🔄")
                await asyncio.sleep(delay)
            else:
                log_error(f"All {max_retries} retry attempts failed: {e}")
        except Exception as e:
            # Non-retryable error, raise immediately
            raise

    raise last_exception


class AgentLoop4:
    def __init__(self, multi_mcp, strategy="conservative"):
        self.multi_mcp = multi_mcp
        self.strategy_name = strategy
        self.agent_runner = AgentRunner(multi_mcp)
        self.context = None  # Reference for external stopping
        self._tasks = set()  # Track active async tasks for immediate cancellation
        self._query_approval_event = None  # asyncio.Event for query approval gate
        self._pending_queries = None
        self._approved_queries = None
        
        # Load profile for strategy settings
        from core.profile_loader import get_profile
        self.profile = get_profile()
        self.max_steps = self.profile.get("strategy.max_steps", 20)

    def stop(self):
        """Request execution stop"""
        if self.context:
            self.context.stop()
        # Immediately cancel all tracked tasks
        for t in list(self._tasks):
            if not t.done():
                t.cancel()

    async def _track_task(self, coro_or_future):
        """Track an async task or future so it can be cancelled immediately on stop()"""
        if asyncio.iscoroutine(coro_or_future):
            task = asyncio.create_task(coro_or_future)
        else:
            # It's already a task or future (like from asyncio.gather)
            task = coro_or_future
            
        self._tasks.add(task)
        try:
            return await task
        except asyncio.CancelledError:
            raise
        finally:
            self._tasks.discard(task)

    async def resume(self, session_path: str):
        """Resume execution from a saved session file"""
        from pathlib import Path
        
        session_file = Path(session_path)
        if not session_file.exists():
            raise FileNotFoundError(f"Session file not found: {session_file}")
            
        try:
            # 1. Load Context
            self.context = ExecutionContextManager.load_session(session_file)
            self.context.multi_mcp = self.multi_mcp
            
            # 2. Reset Interrupted Nodes
            # Any node that was 'running' or 'stopped' when last saved should be reset to 'pending'
            # so it can be re-executed.
            
            reset_count = 0
            for node_id in self.context.plan_graph.nodes:
                node_data = self.context.plan_graph.nodes[node_id]
                status = node_data.get("status")
                
                if status in ["running", "stopped", "waiting_input"]:
                    node_data["status"] = "pending"
                    log_step(f"🔄 Resetting {node_id} from {status} to pending", symbol="Tg")
                    reset_count += 1
            
            if reset_count > 0:
                self.context._save_session()
                
            log_step(f"✅ Resuming session {self.context.plan_graph.graph['session_id']} ({reset_count} steps reset)", symbol="▶️")
            
            # 3. Execute DAG (WATCHTOWER)
            # Always use current trace context (run_span from process_resume). Skip restoring
            # old trace_id - that fragments the hierarchy (resumed spans end up in a different trace).
            with agent_execute_dag_span(
                session_id=self.context.plan_graph.graph.get("session_id", ""),
                resumed=True,
            ):
                return await self._execute_dag(self.context)
            
        except Exception as e:
            log_error(f"Failed to resume session: {e}")
            raise

    async def run(self, query, file_manifest, globals_schema, uploaded_files, session_id=None, memory_context=None, research_mode="standard", focus_mode=None):
        """
        Main agent loop: bootstrap context with Query node, optionally run file distiller,
        then planning loop (PlannerAgent) -> merge plan -> execute DAG. Handles replanning when
        clarification is resolved.

        WATCHTOWER: Span for the full agent loop.
        - Span name: agent_loop.run
        - Child spans: agent_loop.plan (planner), agent_loop.execute_dag (DAG execution)
        """
        with agent_loop_run_span(session_id or "", query or "") as span:
            span.set_attribute("session_id", session_id or "")
            span.set_attribute("title", "Start the Agent Loop")
            span.set_attribute("query", (query or "")[:100])
            # 🟢 PHASE 0: BOOTSTRAP CONTEXT (Immediate VS Code feedback)
            # We create a temporary graph with just a "Query" node (running Planner) so the UI sees meaningful start
            bootstrap_graph = {
                "nodes": [
                {
                    "id": "Query", 
                    "description": "Formulate execution plan", 
                    "agent": "PlannerAgent", 
                    "status": "running",
                    "reads": ["original_query"],
                    "writes": ["plan_graph"]
                }
                ],
                "edges": [
                    {"source": "ROOT", "target": "Query"}
                ]
            }

            try:
                # Create Context & Save Immediately
                self.context = ExecutionContextManager(
                    bootstrap_graph,
                    session_id=session_id,
                    original_query=query,
                    file_manifest=file_manifest
                )
                self.context.memory_context = memory_context  # Store for retrieval
                # Inject multi_mcp immediately
                self.context.multi_mcp = self.multi_mcp
                self.context.plan_graph.graph['globals_schema'].update(globals_schema)
                self.context.plan_graph.graph['research_mode'] = research_mode
            self.context.plan_graph.graph['focus_mode'] = focus_mode
            self.context._save_session()
                log_step("✅ Session initialized with Query processing", symbol="🌱")
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                print(f"❌ ERROR initializing context: {e}")
                raise

            # Phase 1: File Profiling (if files exist)
            # Run DistillerAgent to profile uploaded files before planning
            file_profiles = {}
            if uploaded_files:
                # Wrap with retry for transient failures
                async def run_distiller():
                    return await self.agent_runner.run_agent(
                        "DistillerAgent",
                        {
                            "task": "profile_files",
                            "files": uploaded_files,
                            "instruction": "Profile and summarize each file's structure, columns, content type",
                            "writes": ["file_profiles"]
                        }
                    )
                file_result = await self._track_task(retry_with_backoff(run_distiller))
                if file_result["success"]:
                    file_profiles = file_result["output"]
                    self.context.set_file_profiles(file_profiles)

            # Phase 2: Planning and Execution Loop
            try:
                while True:
                    if self.context.stop_requested:
                        break

                    # Note: The "Query" node is already 'running' in our bootstrap context

                    # 🧠 Enable System 2 Reasoning for the Planner
                    # This ensures the plan is Verified and Refined before execution

                    async def run_planner():
                        # In standard mode, exclude the deep_research skill so the planner
                    # generates a simple plan instead of a 6-phase deep research pipeline
                    planner_exclude = ["deep_research"] if research_mode != "deep_research" else []
                    return await self.agent_runner.run_agent(
                            "PlannerAgent",
                            {
                                "original_query": query,
                                "planning_strategy": self.strategy_name,
                                "research_mode": research_mode,
                            "focus_mode": focus_mode,
                            "globals_schema": self.context.plan_graph.graph.get("globals_schema", {}),
                                "file_manifest": file_manifest,
                                "file_profiles": file_profiles,
                                "memory_context": memory_context
                            },
                            use_system2=True,
                        exclude_skills=planner_exclude
                        )

                    # WATCHTOWER: Planner phase span
                    with agent_plan_span() as plan_span:
                        def on_plan_retry(attempt):
                            plan_span.set_attribute("retry_attempt", attempt)
                            plan_span.set_attribute("is_retry", True)

                        plan_result = await self._track_task(
                            retry_with_backoff(run_planner, on_retry=on_plan_retry)
                        )
                        attach_plan_graph_to_span(plan_span, plan_result)

                    if self.context.stop_requested:
                        break

                    if not plan_result["success"]:
                        self.context.mark_failed("Query", plan_result['error'])
                        raise RuntimeError(f"Planning failed: {plan_result['error']}")

                # Normalize: if model returned {nodes, edges} at top level instead of {plan_graph: {nodes, edges}}
                if 'plan_graph' not in plan_result['output'] and 'nodes' in plan_result['output'] and 'edges' in plan_result['output']:
                    log_step("Normalizing plan output: wrapping top-level nodes/edges into plan_graph", symbol="🔧")
                    plan_result['output']['plan_graph'] = {
                        'nodes': plan_result['output'].pop('nodes'),
                        'edges': plan_result['output'].pop('edges')
                    }

                    if 'plan_graph' not in plan_result['output']:
                        self.context.mark_failed("Query", "Output missing plan_graph")
                        raise RuntimeError(f"PlannerAgent output missing 'plan_graph' key.")

                    # ===== AUTO-CLARIFICATION CHECK =====
                    AUTO_CLARYFY_THRESHOLD = 0.7
                    confidence = plan_result["output"].get("interpretation_confidence", 1.0)
                    ambiguity_notes = plan_result["output"].get("ambiguity_notes", [])

                    # Check if Planner already added a ClarificationAgent (avoid duplicates)
                    plan_nodes = plan_result["output"]["plan_graph"].get("nodes", [])
                    has_clarification_agent = any(
                        n.get("agent") == "ClarificationAgent" for n in plan_nodes
                    )

                    if confidence < AUTO_CLARYFY_THRESHOLD and ambiguity_notes and not has_clarification_agent:
                        log_step(f"Low confidence ({confidence:.2f}), auto-triggering clarification", symbol="❓")

                        # Get the first step ID from the plan
                        first_step = plan_result["output"].get("next_step_id", "T001")
                        clarification_write_key = "user_clarification_T000"

                        # Create clarification node
                        clarification_node = {
                            "id": "T000_AutoClarify",
                            "agent": "ClarificationAgent",
                            "description": "Clarify ambiguous requirements before proceeding",
                            "agent_prompt": f"The system has identified ambiguities in the user's request. Please ask for clarification on: {'; '.join(ambiguity_notes)}",
                            "reads": [],
                            "writes": [clarification_write_key],
                            "status": "pending"
                        }
                        # Insert the ClarificationAgent node at the start of the plan
                        plan_result["output"]["plan_graph"]["nodes"].insert(0, clarification_node)
                        plan_result["output"]["plan_graph"]["edges"].insert(0, {
                            "source": "T000_AutoClarify",
                            "target": first_step
                        })

                        for node in plan_result["output"]["plan_graph"]["nodes"]:
                            if node.get("id") == first_step:
                                if "reads" not in node:
                                    node["reads"] = []
                                if clarification_write_key not in node["reads"]:
                                    node["reads"].append(clarification_write_key)
                                    log_step(f"Wired {clarification_write_key} into {first_step}'s reads", symbol="🔗")
                                break

                        plan_result["output"]["next_step_id"] = "T000_AutoClarify"
                        log_step(f"Injected ClarificationAgent before {first_step}", symbol="➕")
                    elif has_clarification_agent:
                        log_step(f"Planner already added ClarificationAgent, skipping auto-injection", symbol="ℹ️")

                    # ✅ Mark Query/Planner as Done
                    self.context.plan_graph.nodes["Query"]["output"] = plan_result["output"]
                    self.context.plan_graph.nodes["Query"]["status"] = "completed"
                    self.context.plan_graph.nodes["Query"]["end_time"] = datetime.utcnow().isoformat()

                    # 🟢 PHASE 3: EXPAND GRAPH
                    new_plan_graph = plan_result["output"]["plan_graph"]
                    self._merge_plan_into_context(new_plan_graph)

                try:
                    # Phase 4: Execute DAG (with deep research expansion)
                    if research_mode == "deep_research":
                        await self._track_task(self._expand_deep_research_dag(self.context))
                    else:
                        await self._track_task(self._execute_dag(self.context))

                        if self.context.stop_requested:
                            break

                        if self._should_replan():
                            log_step("♻️ Adaptive Re-planning: Clarification resolved, formulating next steps...", symbol="🔄")
                            self.context.plan_graph.nodes["Query"]["status"] = "running"
                            self.context._save_session()
                            continue
                        else:
                            return self.context

                    except (Exception, asyncio.CancelledError) as e:
                        if isinstance(e, asyncio.CancelledError) or self.context.stop_requested:
                            log_step("🛑 Execution interrupted/stopped.", symbol="🛑")
                            break
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                        print(f"❌ ERROR during execution: {e}")
                        import traceback
                        traceback.print_exc()
                        raise
            except (Exception, asyncio.CancelledError) as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                if self.context:
                    final_status = "stopped" if (self.context.stop_requested or isinstance(e, asyncio.CancelledError)) else "failed"
                    for node_id in self.context.plan_graph.nodes:
                        if self.context.plan_graph.nodes[node_id].get("status") in ["running", "pending"]:
                            self.context.plan_graph.nodes[node_id]["status"] = final_status
                            if final_status == "failed":
                                self.context.plan_graph.nodes[node_id]["error"] = str(e)

                    self.context.plan_graph.graph['status'] = final_status
                    if final_status == "failed":
                        self.context.plan_graph.graph['error'] = str(e)
                    self.context._save_session()
                if not isinstance(e, asyncio.CancelledError) and not self.context.stop_requested:
                    raise e
                return self.context

    def _should_replan(self):
        """
        Check if the graph needs expansion (re-planning).
        Conditions:
        1. All current nodes are finished (completed/skipped).
        2. At least one ClarificationAgent recently completed.
        3. That ClarificationAgent was a 'leaf' (had no successors in the current graph).
        """
        # If any node is still pending/running, we aren't at a dead end yet
        if not self.context.all_done():
            return False
            
        has_new_leaf_clarification = False
        for node_id, node_data in self.context.plan_graph.nodes(data=True):
            if node_data.get("agent") == "ClarificationAgent" and node_data.get("status") == "completed":
                # Check if it was a leaf node (no arrows coming out)
                if not list(self.context.plan_graph.successors(node_id)):
                    has_new_leaf_clarification = True
                    break
        
        return has_new_leaf_clarification

    # ===== DEEP RESEARCH: ENGINE-DRIVEN DAG EXPANSION =====

    async def _expand_deep_research_dag(self, context):
        """
        Engine-driven DAG expansion for deep research mode.

        Replaces PlannerAgent full plan generation with deterministic,
        phase-by-phase graph expansion. Each phase:
        1. Executes current pending nodes
        2. Reads completed outputs
        3. Creates next phase nodes/edges
        4. Merges into graph (UI sees new nodes on next poll)
        5. Executes new nodes

        Phases:
          1: T001 ThinkerAgent (query decomposition) — already in graph
          2: N × RetrieverAgent (parallel search, one per sub-query)
          3: ThinkerAgent (gap analysis)
          4: SummarizerAgent (synthesis with citations)
          5: FormatterAgent (final report)
        """
        focus_mode = context.plan_graph.graph.get('focus_mode')
        original_query = context.plan_graph.graph.get('original_query', '')

        # ── Strip planner's nodes beyond T001 ──
        # The PlannerAgent creates a full plan (T001-T00N), but deep research mode
        # replaces T002+ with engine-controlled nodes. If we don't remove them,
        # _execute_dag will run the planner's T002-T00N with wrong prompts
        # before the engine gets a chance to create its own.
        keep_nodes = {"ROOT", "Query", "T001"}
        remove_ids = [n for n in context.plan_graph.nodes if n not in keep_nodes]
        for node_id in remove_ids:
            context.plan_graph.remove_node(node_id)
        if remove_ids:
            log_step(f"Stripped {len(remove_ids)} planner nodes — engine will rebuild phases 2-6", symbol="🔧")

        # ── Override T001 prompt with improved research decomposition ──
        if "T001" in context.plan_graph.nodes:
            focus_instruction = ""
            if focus_mode:
                focus_labels = {
                    "academic": "Focus on academic and scholarly angles — peer-reviewed research, theoretical frameworks, key researchers, institutions, and landmark papers.",
                    "news": "Focus on recent events, breaking developments, policy changes, and current affairs angles.",
                    "code": "Focus on technical implementation, APIs, libraries, frameworks, code architecture, and developer ecosystem.",
                    "finance": "Focus on financial aspects — market data, companies, valuations, economic impact, investment angles, and regulatory landscape.",
                    "writing": "Focus on narrative craft, communication styles, audience analysis, and editorial perspectives.",
                }
                focus_instruction = (
                    f"\nFOCUS MODE: {focus_mode.upper()}\n"
                    f"{focus_labels.get(focus_mode, 'Apply general research best practices.')}\n"
                    f"Weight your queries toward this focus while still maintaining breadth.\n"
                )

            context.plan_graph.nodes["T001"]["agent_prompt"] = (
                f"You are a research strategist. Decompose the following query into 5-8 comprehensive "
                f"sub-queries that independent search agents will execute in parallel.\n\n"
                f"QUERY: '{original_query}'\n"
                f"{focus_instruction}\n"
                f"STRATEGY:\n"
                f"- Consider every plausible interpretation and domain the query could refer to\n"
                f"- For each domain, cover: definitions & fundamentals, technical depth, types & classifications, "
                f"key players & real-world applications, recent trends\n"
                f"- If the query implies geographic, temporal, or industry context, add queries scoped to that context\n"
                f"- Include one synthesis query that compares/contrasts across identified domains\n"
                f"- Each sub-query must be a complete, self-contained search string\n\n"
                f"OUTPUT: JSON with key 'decomposed_queries' — a list of "
                f"{{\"query\": \"<full search string>\", \"dimension\": \"<short label>\"}}"
            )

        # ── Phase 1: Execute T001 (ThinkerAgent — Query Decomposition) ──
        log_step("Deep Research Phase 1: Query decomposition", symbol="🔬")
        await self._track_task(self._execute_dag(context))

        if context.stop_requested:
            return

        # Check T001 completed
        t001_data = context.plan_graph.nodes.get("T001", {})
        if t001_data.get("status") != "completed":
            log_error(f"T001 did not complete (status: {t001_data.get('status')}). Cannot expand.")
            return

        # Extract sub-queries
        gs = context.plan_graph.graph['globals_schema']
        decomposed_raw = gs.get("decomposed_queries_T001")
        sub_queries = self._extract_sub_queries(decomposed_raw)

        if not sub_queries:
            log_step("No sub-queries extracted, falling back to original query", symbol="⚠️")
            sub_queries = [{"query": original_query, "dimension": "general"}]

        sub_queries = sub_queries[:8]  # Cap at 8
        num_queries = len(sub_queries)
        log_step(f"Decomposed into {num_queries} sub-queries", symbol="📋")

        # ── Query Approval Gate ──
        # Pause and wait for user to approve decomposed queries before spawning retrievers
        self._query_approval_event = asyncio.Event()
        self._pending_queries = sub_queries
        self._approved_queries = None

        await event_bus.publish("query_approval_required", "AgentLoop4", {
            "run_id": context.plan_graph.graph.get("session_id", ""),
            "queries": sub_queries,
            "original_query": original_query,
        })
        log_step("Waiting for user to approve research queries...", symbol="⏳")

        await self._query_approval_event.wait()

        # Use approved queries (may have been modified by user) or fallback to original
        if self._approved_queries is not None:
            sub_queries = self._approved_queries
            num_queries = len(sub_queries)
            log_step(f"User approved {num_queries} queries", symbol="✅")

        self._query_approval_event = None
        self._pending_queries = None
        self._approved_queries = None

        # ── Phase 2: Create N RetrieverAgent Nodes (Parallel) ──
        retriever_nodes = []
        retriever_edges = []
        retriever_ids = []
        retriever_write_keys = []

        for i, sq in enumerate(sub_queries):
            node_id = f"T{str(i + 2).zfill(3)}"  # T002, T003, ...
            q_text = sq.get("query", original_query) if isinstance(sq, dict) else str(sq)
            dimension = sq.get("dimension", f"dim_{i+1}") if isinstance(sq, dict) else f"dim_{i+1}"
            write_key = f"initial_sources_{node_id}"

            retriever_nodes.append({
                "id": node_id,
                "description": f"Search: {dimension}"[:120],
                "agent": "RetrieverAgent",
                "agent_prompt": self._build_retriever_prompt(q_text, focus_mode),
                "reads": ["decomposed_queries_T001"],
                "writes": [write_key],
                "status": "pending"
            })
            retriever_edges.append({"source": "T001", "target": node_id})
            retriever_ids.append(node_id)
            retriever_write_keys.append(write_key)

        self._merge_plan_into_context({"nodes": retriever_nodes, "edges": retriever_edges})
        await event_bus.publish("dag_expanded", "AgentLoop4", {
            "phase": 2, "new_nodes": retriever_ids,
            "message": f"Searching {num_queries} dimensions with 15 URLs each"
        })

        log_step(f"Deep Research Phase 2: {num_queries} parallel searches", symbol="🔍")
        await self._execute_steps_parallel(context, retriever_ids)

        if context.stop_requested:
            return

        # Filter to only successfully completed retrievers
        successful_ids = [rid for rid in retriever_ids
                          if context.plan_graph.nodes.get(rid, {}).get("status") == "completed"]
        successful_write_keys = [f"initial_sources_{rid}" for rid in successful_ids]

        if not successful_ids:
            log_error("All RetrieverAgents failed. Cannot continue deep research.")
            return

        # ── Phase 3: Gap Analysis ThinkerAgent ──
        gap_id = f"T{str(num_queries + 2).zfill(3)}"
        gap_analysis_key = f"gap_analysis_{gap_id}"

        gap_node = {
            "id": gap_id,
            "description": "Analyze gaps and contradictions across sources",
            "agent": "ThinkerAgent",
            "agent_prompt": (
                f"Analyze all collected research sources for coverage gaps, contradictions, "
                f"and weak evidence. Read: {', '.join(successful_write_keys)}. "
                f"Original query: '{original_query}'. "
                f"Output JSON with: 'gap_analysis' (string summary of gaps found), "
                f"'followup_queries' (list of 1-3 targeted search queries to fill the most critical gaps), "
                f"'contradictions' (list of conflicting claims between sources)."
            ),
            "reads": successful_write_keys,
            "writes": [gap_analysis_key],
            "status": "pending"
        }
        gap_edges = [{"source": rid, "target": gap_id} for rid in successful_ids]

        self._merge_plan_into_context({"nodes": [gap_node], "edges": gap_edges})
        await event_bus.publish("dag_expanded", "AgentLoop4", {
            "phase": 3, "new_nodes": [gap_id],
            "message": "Analyzing gaps and contradictions"
        })

        log_step(f"Deep Research Phase 3: Gap analysis ({gap_id})", symbol="🔎")
        await self._track_task(self._execute_dag(context))

        if context.stop_requested:
            return

        # ── Phase 4: Targeted Deep Search (follow-up queries from gap analysis) ──
        deep_write_keys = []
        followup_ids = []
        followup_queries = self._extract_followup_queries(context, gap_analysis_key)
        node_offset = num_queries + 3  # next available node number

        if followup_queries:
            followup_nodes = []
            followup_edges = []

            for i, fq in enumerate(followup_queries):
                fq_id = f"T{str(node_offset + i).zfill(3)}"
                fq_write_key = f"deep_sources_{fq_id}"
                followup_nodes.append({
                    "id": fq_id,
                    "description": f"Deep search: {fq[:80]}",
                    "agent": "RetrieverAgent",
                    "agent_prompt": self._build_retriever_prompt(fq, focus_mode),
                    "reads": [gap_analysis_key],
                    "writes": [fq_write_key],
                    "status": "pending"
                })
                followup_edges.append({"source": gap_id, "target": fq_id})
                followup_ids.append(fq_id)
                deep_write_keys.append(fq_write_key)

            self._merge_plan_into_context({"nodes": followup_nodes, "edges": followup_edges})
            await event_bus.publish("dag_expanded", "AgentLoop4", {
                "phase": 4, "new_nodes": followup_ids,
                "message": f"Deep searching {len(followup_queries)} follow-up queries"
            })

            log_step(f"Deep Research Phase 4: {len(followup_queries)} targeted follow-up searches", symbol="🔬")
            await self._execute_steps_parallel(context, followup_ids)
            node_offset += len(followup_queries)

            if context.stop_requested:
                return

            # Filter to successfully completed follow-up retrievers
            deep_write_keys = [f"deep_sources_{fid}" for fid in followup_ids
                               if context.plan_graph.nodes.get(fid, {}).get("status") == "completed"]
        else:
            log_step("Deep Research Phase 4: No follow-up queries needed — skipping", symbol="⏩")

        # ── Build source index and pre-process sources before synthesis ──
        all_retriever_keys = successful_write_keys + deep_write_keys
        self._build_source_index(context, all_retriever_keys)
        self._preprocess_sources(context, all_retriever_keys, sub_queries)

        # ── Phase 5: SummarizerAgent ──
        synth_id = f"T{str(node_offset).zfill(3)}"
        synth_key = f"research_synthesis_{synth_id}"
        synth_reads = ["processed_sources", "source_index", gap_analysis_key]

        # Build focus-mode-specific synthesis instructions
        focus_synth_extra = ""
        if focus_mode == "code":
            focus_synth_extra = (
                "FOCUS MODE: CODE. You MUST preserve ALL code blocks from sources. "
                "Wrap every code snippet in fenced markdown code blocks with the correct language tag "
                "(```python, ```javascript, etc.). Include complete function signatures, class definitions, "
                "and usage examples. Do NOT paraphrase or summarize code — include it verbatim. "
                "Organize code examples by dimension/topic. For each code block, explain what it does "
                "and cite its source using [[N]](url). "
            )

        synth_node = {
            "id": synth_id,
            "description": "Synthesize all sources into cited narrative",
            "agent": "SummarizerAgent",
            "agent_prompt": (
                f"Synthesize ALL research sources into a comprehensive, exhaustive narrative. "
                f"Read 'processed_sources' (organized by research dimension with excerpts) "
                f"and 'source_index' (mapping source numbers to REAL URLs and titles). "
                f"Original query: '{original_query}'. "
                f"{focus_synth_extra}"
                f"Cover EVERY research dimension. Cite EVERY source using [[N]](url) format "
                f"where url is the ACTUAL URL from source_index or processed_sources — "
                f"NEVER use example.com or any placeholder/made-up URL. "
                f"Each source in processed_sources has 'url' and 'index' fields — use those exact URLs. "
                f"Include per-paragraph confidence scoring (HIGH/MEDIUM/LOW). "
                f"Surface contradictions explicitly. Minimum 1500 words."
            ),
            "reads": synth_reads,
            "writes": [synth_key],
            "status": "pending"
        }

        # Wire synthesis to gap analysis + all follow-up retrievers
        synth_edges = [{"source": gap_id, "target": synth_id}]
        for fid in followup_ids:
            synth_edges.append({"source": fid, "target": synth_id})

        self._merge_plan_into_context({
            "nodes": [synth_node],
            "edges": synth_edges
        })
        await event_bus.publish("dag_expanded", "AgentLoop4", {
            "phase": 5, "new_nodes": [synth_id],
            "message": "Synthesizing sources with citations"
        })

        log_step(f"Deep Research Phase 5: Synthesis ({synth_id})", symbol="📝")
        await self._track_task(self._execute_dag(context))

        if context.stop_requested:
            return

        # ── Phase 6: FormatterAgent ──
        fmt_id = f"T{str(node_offset + 1).zfill(3)}"
        fmt_key = f"formatted_report_{fmt_id}"

        # Build focus-mode-specific formatter instructions
        focus_fmt_extra = ""
        if focus_mode == "code":
            focus_fmt_extra = (
                "FOCUS MODE: CODE. The report MUST include ALL code blocks from the synthesis. "
                "Preserve every fenced code block verbatim — do NOT remove, truncate, or summarize code. "
                "Use proper syntax highlighting (```python, ```javascript, etc.). "
                "Add a dedicated '## Code Examples' or '## Implementation' section grouping all code snippets. "
                "For each code block include: source citation, language, and brief explanation. "
            )

        fmt_node = {
            "id": fmt_id,
            "description": "Format final research report",
            "agent": "FormatterAgent",
            "agent_prompt": (
                f"Generate the final research report from available data. "
                f"Original query: '{original_query}'. "
                f"Use all_globals_schema to find ALL available data even if some phases were incomplete. "
                f"{focus_fmt_extra}"
                f"Include: executive summary, key findings with confidence levels, "
                f"detailed analysis, methodology, and clickable citation list. "
                f"CRITICAL: Use source_index to get REAL URLs for citations — NEVER use example.com or placeholder URLs. "
                f"Preserve all [[N]](url) citations from the synthesis exactly as-is. "
                f"If some data is missing, note it but still produce the best report possible. "
                f"Output the report under BOTH 'markdown_report' AND '{fmt_key}' keys in your JSON response."
            ),
            "reads": [synth_key, "source_index"],
            "writes": [fmt_key],
            "status": "pending"
        }

        self._merge_plan_into_context({
            "nodes": [fmt_node],
            "edges": [{"source": synth_id, "target": fmt_id}]
        })
        await event_bus.publish("dag_expanded", "AgentLoop4", {
            "phase": 6, "new_nodes": [fmt_id],
            "message": "Generating final report"
        })

        log_step(f"Deep Research Phase 6: Report formatting ({fmt_id})", symbol="📄")
        await self._track_task(self._execute_dag(context))

        # ── Fallback: Ensure FormatterAgent always produces output ──
        fmt_status = context.plan_graph.nodes.get(fmt_id, {}).get("status")
        if fmt_status != "completed":
            log_step("FormatterAgent didn't complete — running fallback with available data", symbol="⚠️")
            # Reset formatter to pending and clear dependency edges so it can run
            if fmt_id in context.plan_graph.nodes:
                context.plan_graph.nodes[fmt_id]["status"] = "pending"
                context.plan_graph.nodes[fmt_id]["error"] = None
            # Remove incoming edges so get_ready_steps() won't block on failed predecessors
            predecessors = list(context.plan_graph.predecessors(fmt_id))
            for pred in predecessors:
                context.plan_graph.remove_edge(pred, fmt_id)
            await self._track_task(self._execute_dag(context))

        # ── Post-process: Fix citations with real URLs from source_index ──
        self._fix_citations(context, synth_key)
        self._fix_citations(context, fmt_key)

        log_step("Deep research complete", symbol="✅")

    def _fix_citations(self, context, output_key: str):
        """Post-process markdown to replace placeholder/fake URLs with real source_index URLs.

        Handles these patterns:
          [[N]](any-url)  → [[N]](real-url)
          [[N]]           → [[N]](real-url)
          [N]             → [[N]](real-url) (only bare numeric refs)
        """
        import re as _re

        gs = context.plan_graph.graph.get('globals_schema', {})
        source_index = gs.get("source_index", {})
        if not source_index:
            return

        text = gs.get(output_key)
        if not text or not isinstance(text, str):
            # Also check node output for markdown_report
            for node_id in context.plan_graph.nodes:
                node = context.plan_graph.nodes[node_id]
                out = node.get("output", {})
                if isinstance(out, dict):
                    text = out.get("markdown_report") or out.get(output_key)
                    if text and isinstance(text, str):
                        break
            if not text or not isinstance(text, str):
                return

        original_text = text

        # Pattern 1: [[N]](url) → replace url with real one
        def replace_bracketed_with_url(match):
            n = match.group(1)
            src = source_index.get(n) or source_index.get(str(n))
            if src and src.get("url"):
                title = src.get("title", f"Source {n}")
                return f"[[{n}] {title}]({src['url']})"
            return match.group(0)

        text = _re.sub(r'\[\[(\d+)\]\]\([^)]*\)', replace_bracketed_with_url, text)

        # Pattern 2: [[N]] without URL → add real URL
        def replace_bracketed_no_url(match):
            n = match.group(1)
            src = source_index.get(n) or source_index.get(str(n))
            if src and src.get("url"):
                title = src.get("title", f"Source {n}")
                return f"[[{n}] {title}]({src['url']})"
            return match.group(0)

        text = _re.sub(r'\[\[(\d+)\]\](?!\()', replace_bracketed_no_url, text)

        # Pattern 3: bare [N] (single bracket, not already [[N]]) → [[N] Title](real-url)
        # Negative lookbehind for [ to avoid re-matching [[N]] patterns already handled above
        # Negative lookahead for ] and ( to avoid matching [N](url) or [N][ref]
        def replace_bare_ref(match):
            n = match.group(1)
            src = source_index.get(n) or source_index.get(str(n))
            if src and src.get("url"):
                title = src.get("title", f"Source {n}")
                return f"[[{n}] {title}]({src['url']})"
            return match.group(0)

        text = _re.sub(r'(?<!\[)\[(\d{1,2})\](?!\(|\[|\])', replace_bare_ref, text)

        if text != original_text:
            # Update in globals_schema
            gs[output_key] = text
            # Update in node output
            for node_id in context.plan_graph.nodes:
                node = context.plan_graph.nodes[node_id]
                out = node.get("output", {})
                if isinstance(out, dict):
                    if "markdown_report" in out and isinstance(out["markdown_report"], str):
                        out["markdown_report"] = self._apply_citation_fix(out["markdown_report"], source_index)
                    if output_key in out and isinstance(out[output_key], str):
                        out[output_key] = self._apply_citation_fix(out[output_key], source_index)
            log_step(f"Fixed citations in {output_key} with real URLs from source_index", symbol="🔗")

    def _apply_citation_fix(self, text: str, source_index: dict) -> str:
        """Apply citation URL replacement to a text string."""
        import re as _re

        def replace_with_url(match):
            n = match.group(1)
            src = source_index.get(n) or source_index.get(str(n))
            if src and src.get("url"):
                title = src.get("title", f"Source {n}")
                return f"[[{n}] {title}]({src['url']})"
            return match.group(0)

        # Replace [[N]](any-url) with real URL
        text = _re.sub(r'\[\[(\d+)\]\]\([^)]*\)', replace_with_url, text)
        # Replace [[N]] without URL
        text = _re.sub(r'\[\[(\d+)\]\](?!\()', replace_with_url, text)
        # Replace [[N] any-title](any-url) with real URL
        text = _re.sub(r'\[\[(\d+)\][^\]]*\]\([^)]*\)', replace_with_url, text)
        # Replace bare [N] (single bracket) with real URL
        text = _re.sub(r'(?<!\[)\[(\d{1,2})\](?!\(|\[|\])', replace_with_url, text)
        return text

    def _extract_sub_queries(self, decomposed_raw) -> list:
        """Robustly extract sub-queries from ThinkerAgent T001 output."""
        import json as _json

        if decomposed_raw is None:
            return []

        # String → parse
        if isinstance(decomposed_raw, str):
            try:
                decomposed_raw = _json.loads(decomposed_raw)
            except (_json.JSONDecodeError, TypeError):
                return []

        # List → validate items
        if isinstance(decomposed_raw, list):
            result = []
            for item in decomposed_raw:
                if isinstance(item, dict) and "query" in item:
                    result.append(item)
                elif isinstance(item, str):
                    result.append({"query": item, "dimension": "general"})
            return result

        # Dict → look for 'decomposed_queries' key
        if isinstance(decomposed_raw, dict):
            queries = decomposed_raw.get("decomposed_queries")
            if queries:
                return self._extract_sub_queries(queries)
            # Nested output
            nested = decomposed_raw.get("output")
            if isinstance(nested, dict):
                queries = nested.get("decomposed_queries")
                if queries:
                    return self._extract_sub_queries(queries)

        return []

    def _extract_followup_queries(self, context, gap_analysis_key: str) -> list:
        """Extract follow-up queries from gap analysis output. Returns list of query strings, capped at 3."""
        import json as _json

        gs = context.plan_graph.graph.get('globals_schema', {})
        raw = gs.get(gap_analysis_key)
        if raw is None:
            return []

        # String → parse
        if isinstance(raw, str):
            try:
                raw = _json.loads(raw)
            except (_json.JSONDecodeError, TypeError):
                return []

        # Dict → look for followup_queries key (or variants)
        if isinstance(raw, dict):
            for key in ("followup_queries", "follow_up_queries", "deep_queries", "targeted_queries"):
                queries = raw.get(key)
                if queries and isinstance(queries, list):
                    result = [q if isinstance(q, str) else q.get("query", str(q)) for q in queries]
                    return [q for q in result if q.strip()][:3]
            # Check nested output
            nested = raw.get("output")
            if isinstance(nested, dict):
                return self._extract_followup_queries(context, gap_analysis_key)

        return []

    def _auto_build_source_index(self, context):
        """Auto-build source_index from ALL completed RetrieverAgent outputs.
        Called after each RetrieverAgent completes in _execute_dag.
        Works for both standard and deep research modes.
        """
        # Collect write keys from all completed RetrieverAgent nodes
        retriever_write_keys = []
        for node_id, node_data in context.plan_graph.nodes(data=True):
            if node_id == "ROOT":
                continue
            if node_data.get("agent") == "RetrieverAgent" and node_data.get("status") == "completed":
                retriever_write_keys.extend(node_data.get("writes", []))

        if retriever_write_keys:
            self._build_source_index(context, retriever_write_keys)

    def _build_source_index(self, context, write_keys: list) -> dict:
        """Build a deduplicated source index from retriever outputs.
        Returns: {"1": {"url": "...", "title": "...", "snippet": "..."}, ...}
        Also stores it in globals_schema["source_index"].
        """
        import json as _json

        gs = context.plan_graph.graph.get('globals_schema', {})
        seen_urls = set()
        source_index = {}
        counter = 1

        for key in write_keys:
            raw = gs.get(key)
            if raw is None:
                continue

            # Parse if string
            if isinstance(raw, str):
                try:
                    raw = _json.loads(raw)
                except (_json.JSONDecodeError, TypeError):
                    continue

            # Handle dict wrapper: some retrievers return {"key": [sources]}
            # or MCP TextContent format: {"content": [{"type": "text", "text": "[{sources}]"}]}
            if isinstance(raw, dict):
                # Unwrap MCP TextContent format first
                content_list = raw.get("content")
                if isinstance(content_list, list) and content_list:
                    first = content_list[0]
                    if isinstance(first, dict) and first.get("type") == "text" and "text" in first:
                        # This is MCP TextContent — parse the inner JSON text
                        try:
                            raw = _json.loads(first["text"])
                        except (_json.JSONDecodeError, TypeError):
                            continue
                    else:
                        # Regular dict wrapper — look for the first list value
                        raw = content_list
                else:
                    # Look for the first list value inside the dict
                    for v in raw.values():
                        if isinstance(v, list) and v:
                            raw = v
                            break
                    else:
                        continue

            # Handle list of source dicts or URL strings
            sources = raw if isinstance(raw, list) else []
            for src in sources:
                if isinstance(src, str):
                    # Plain URL string — add with no content
                    url = src.strip()
                    if url and url.startswith("http") and url not in seen_urls:
                        seen_urls.add(url)
                        source_index[str(counter)] = {
                            "url": url,
                            "title": "",
                            "snippet": ""
                        }
                        counter += 1
                elif isinstance(src, dict):
                    url = src.get("url", "")
                    if not url or url in seen_urls:
                        continue
                    content = src.get("content", "")
                    if isinstance(content, str) and content.startswith("[error]"):
                        continue
                    seen_urls.add(url)
                    source_index[str(counter)] = {
                        "url": url,
                        "title": src.get("title", ""),
                        "snippet": content[:200] if isinstance(content, str) else ""
                    }
                    counter += 1

        gs["source_index"] = source_index
        log_step(f"Built source index: {len(source_index)} unique sources", symbol="📋")
        return source_index

    def _preprocess_sources(self, context, write_keys: list, sub_queries: list) -> list:
        """Pre-process retriever outputs into organized, deduplicated structure by dimension.
        Returns list of dimension dicts and stores as globals_schema["processed_sources"].
        """
        import json as _json

        gs = context.plan_graph.graph.get('globals_schema', {})
        source_index = gs.get("source_index", {})

        # Build reverse lookup: url -> source index number
        url_to_index = {}
        for idx, info in source_index.items():
            url_to_index[info.get("url", "")] = idx

        # Map write_keys to dimensions from sub_queries
        dimensions = []
        for i, key in enumerate(write_keys):
            dim_label = "general"
            if i < len(sub_queries):
                sq = sub_queries[i]
                dim_label = sq.get("dimension", f"dimension_{i+1}") if isinstance(sq, dict) else f"dimension_{i+1}"

            raw = gs.get(key)
            if raw is None:
                continue
            if isinstance(raw, str):
                try:
                    raw = _json.loads(raw)
                except (_json.JSONDecodeError, TypeError):
                    continue

            # Unwrap MCP TextContent format: {"content": [{"type": "text", "text": "[{sources}]"}]}
            if isinstance(raw, dict):
                content_list = raw.get("content")
                if isinstance(content_list, list) and content_list:
                    first = content_list[0]
                    if isinstance(first, dict) and first.get("type") == "text" and "text" in first:
                        try:
                            raw = _json.loads(first["text"])
                        except (_json.JSONDecodeError, TypeError):
                            continue

            sources = raw if isinstance(raw, list) else []
            dim_sources = []
            for src in sources:
                if not isinstance(src, dict):
                    continue
                url = src.get("url", "")
                content = src.get("content", "")
                if content.startswith("[error]") or not url:
                    continue
                idx = url_to_index.get(url, "?")
                # Code focus mode: larger excerpts to preserve code blocks
                focus = context.plan_graph.graph.get('focus_mode', '')
                max_chars = 12000 if focus == "code" else 4000
                dim_sources.append({
                    "index": idx,
                    "url": url,
                    "title": src.get("title", ""),
                    "excerpt": content[:max_chars]
                })

            if dim_sources:
                dimensions.append({
                    "dimension": dim_label,
                    "sources": dim_sources
                })

        gs["processed_sources"] = dimensions
        total = sum(len(d["sources"]) for d in dimensions)
        log_step(f"Pre-processed sources: {total} sources across {len(dimensions)} dimensions", symbol="📊")
        return dimensions

    def _build_retriever_prompt(self, query_text: str, focus_mode: str = None) -> str:
        """Build RetrieverAgent prompt with optional focus_mode constraints."""
        prompt = (
            f"Search for: '{query_text}'. "
            f"Use search_web_with_text_content with string='{query_text}'"
        )

        focus_constraints = {
            "academic": (
                " site:scholar.google.com OR site:arxiv.org OR site:pubmed.ncbi.nlm.nih.gov",
                "Prioritize peer-reviewed papers and academic sources. Format citations in APA."
            ),
            "news": (
                " news OR latest OR breaking",
                "Prioritize recent news from the last 7 days. Include publication dates."
            ),
            "code": (
                " site:github.com OR site:stackoverflow.com OR documentation",
                "Prioritize code repositories and technical docs. Extract code snippets."
            ),
            "finance": (
                " site:sec.gov OR financial report OR earnings",
                "Prioritize financial data, SEC filings, market data. Extract numbers."
            ),
            "writing": (
                "",
                "Focus on editorial content, style guides, writing techniques."
            ),
        }

        if focus_mode and focus_mode in focus_constraints:
            search_suffix, instruction = focus_constraints[focus_mode]
            if search_suffix:
                prompt += f". Append to search: '{search_suffix}'"
            prompt += f" {instruction}"

        prompt += (
            " and integer=15. "
            "Return all results with URLs, titles, and extracted text."
        )
        return prompt

    async def _direct_web_search(self, query: str, limit: int = 5) -> str:
        """Direct web search bypassing MCP server for parallel deep research.
        Replicates search_web_with_text_content logic from server_browser.py.
        Returns JSON string of results (same format as MCP tool output).
        """
        import json as _json
        from mcp_servers.tools.switch_search_method import smart_search
        from mcp_servers.tools.web_tools_async import smart_web_extract

        EXTRACT_TIMEOUT = 8

        async def _extract_single(url: str, rank: int) -> dict:
            try:
                web_result = await asyncio.wait_for(smart_web_extract(url), timeout=EXTRACT_TIMEOUT)
                text = web_result.get("best_text", "")[:8000]
                text = text.replace('\n', ' ').replace('  ', ' ').strip()
                return {
                    "url": url,
                    "title": web_result.get("title", ""),
                    "content": text if text else "[error] No readable content found",
                    "images": web_result.get("images", []),
                    "rank": rank
                }
            except asyncio.TimeoutError:
                return {"url": url, "title": "", "content": f"[error] Timeout after {EXTRACT_TIMEOUT}s", "rank": rank}
            except Exception as e:
                return {"url": url, "title": "", "content": f"[error] {str(e)}", "rank": rank}

        try:
            limit = min(max(limit, 1), 20)
            urls = await smart_search(query, limit)

            if not urls:
                return _json.dumps([{"url": "", "title": "", "content": "[error] No search results found", "rank": 1}])

            target_urls = urls[:limit]
            tasks = [_extract_single(url, i + 1) for i, url in enumerate(target_urls)]
            results = await asyncio.gather(*tasks)
            results = sorted(results, key=lambda r: r["rank"])
            return _json.dumps(results)
        except Exception as e:
            return _json.dumps([{"url": "", "title": "", "content": f"[error] {str(e)}", "rank": 1}])

    async def _emit_source_progress_helper(self, step_id, total_sources):
        """Emit source reading progress events for the UI."""
        interval = max(0.6, 8.0 / total_sources)
        for i in range(1, total_sources + 1):
            await asyncio.sleep(interval)
            await event_bus.publish("source_progress", "AgentLoop4", {
                "step_id": step_id,
                "current": i,
                "total": total_sources,
                "message": f"Reading source {i}/{total_sources}..."
            })

    def _merge_plan_into_context(self, new_plan_graph):
        """Merge the planned nodes into the existing bootstrap context"""
        new_nodes = new_plan_graph.get("nodes", [])
        new_edges = new_plan_graph.get("edges", [])

        # Track which new nodes have incoming edges to detect orphans
        nodes_with_incoming_edges = set()
        # Track successfully added node IDs (to skip edges referencing rejected nodes)
        added_node_ids = set(self.context.plan_graph.nodes)  # includes existing nodes (ROOT, Query)

        # Build set of valid agent types from registry
        from core.registry import AgentRegistry
        valid_agents = set(AgentRegistry.list_agents().keys())

        # Add new nodes
        for node in new_nodes:
            # Validate agent type — reject hallucinated agents before they enter the graph
            agent_type = node.get("agent", "")
            if agent_type and agent_type not in valid_agents:
                log_step(f"Invalid agent '{agent_type}' in plan node {node.get('id', '?')} — skipping (valid: {', '.join(sorted(valid_agents))})", symbol="⚠️")
                continue

            # Prepare node data with defaults
            node_data = node.copy()
            # Set defaults if not present in the plan
            defaults = {
                'status': 'pending',
                'output': None,
                'error': None,
                'cost': 0.0,
                'start_time': None,
                'end_time': None,
                'execution_time': 0.0
            }
            for k, v in defaults.items():
                node_data.setdefault(k, v)

            # Avoid overwriting already completed nodes if they somehow appear in the new plan
            if node["id"] in self.context.plan_graph:
                 existing_status = self.context.plan_graph.nodes[node["id"]].get("status")
                 if existing_status == "completed":
                      continue

            self.context.plan_graph.add_node(node["id"], **node_data)
            added_node_ids.add(node["id"])

        # Add new edges (redirect ROOT -> First Step to Query -> First Step)
        for edge in new_edges:
            # Robustly handle different edge formats: list [src, tgt] or dict {source, target}
            if isinstance(edge, (list, tuple)) and len(edge) >= 2:
                source, target = str(edge[0]), str(edge[1])
            elif isinstance(edge, dict):
                source = edge.get("source") or edge.get("from")
                target = edge.get("target") or edge.get("to")
            else:
                log_step(f"⚠️ Skipping malformed edge: {edge}", symbol="⚠️")
                continue

            if not source or not target:
                log_step(f"⚠️ Skipping malformed edge: {edge}", symbol="⚠️")
                continue

            # Redirect dependencies: If a node depends on ROOT, make it depend on Query
            if source == "ROOT":
                source = "Query"

            # Skip edges referencing rejected/non-existent nodes to prevent phantom nodes
            if source not in added_node_ids or target not in added_node_ids:
                log_step(f"⚠️ Skipping edge {source}→{target}: references node not in graph", symbol="⚠️")
                continue

            self.context.plan_graph.add_edge(source, target)
            nodes_with_incoming_edges.add(target)
        
        # 🛡️ AUTO-CONNECT: If a new node has NO incoming edges, connect it to "Query"
        # This fixes cases where PlannerAgent returns nodes but forgets the edges
        for node in new_nodes:
            if node["id"] in added_node_ids and node["id"] not in nodes_with_incoming_edges:
                log_step(f"🔗 Auto-connected orphan node {node['id']} to Query", symbol="🔗")
                self.context.plan_graph.add_edge("Query", node["id"])
        
        # 🔧 SAFETY NET: Ensure ClarificationAgent outputs are wired to successor nodes
        # This fixes cases where Planner adds a ClarificationAgent but forgets to wire reads
        for node in new_nodes:
            if node.get("agent") == "ClarificationAgent":
                clarification_node_id = node["id"]
                clarification_writes = node.get("writes", [])
                
                if not clarification_writes:
                    continue
                    
                # Find all successor nodes (nodes that this ClarificationAgent points to)
                for edge in new_edges:
                    if edge.get("source") == clarification_node_id:
                        successor_id = edge.get("target")
                        if not successor_id:
                            continue
                        
                        # Find the successor node and ensure it reads from clarification
                        for succ_node in new_nodes:
                            if succ_node.get("id") == successor_id:
                                if "reads" not in succ_node:
                                    succ_node["reads"] = []
                                
                                for write_key in clarification_writes:
                                    if write_key not in succ_node["reads"]:
                                        succ_node["reads"].append(write_key)
                                        log_step(f"🔗 Auto-wired {write_key} into {successor_id}'s reads", symbol="🔗")
                                        
                                        # Also update the node in the graph if already added
                                        if successor_id in self.context.plan_graph:
                                            if "reads" not in self.context.plan_graph.nodes[successor_id]:
                                                self.context.plan_graph.nodes[successor_id]["reads"] = []
                                            if write_key not in self.context.plan_graph.nodes[successor_id]["reads"]:
                                                self.context.plan_graph.nodes[successor_id]["reads"].append(write_key)
                                break
        
        self.context._save_session()
        log_step("✅ Plan merged into execution context", symbol="🌳")

    async def _execute_dag(self, context):
        """Execute DAG with visualization - DEBUGGING MODE"""
        
        # Get plan_graph structure for visualization
        plan_graph = {
            "nodes": [
                {"id": node_id, **node_data} 
                for node_id, node_data in context.plan_graph.nodes(data=True)
            ],
            "links": [
                {"source": source, "target": target}
                for source, target in context.plan_graph.edges()
            ]
        }
        
        # Create visualizer
        visualizer = ExecutionVisualizer(plan_graph)
        console = Console()
        
        # 🔧 DEBUGGING MODE: No Live display, just regular prints
        # Each DAG step needs one iteration, plus headroom for retries (MAX_STEP_RETRIES=2 per step).
        # Deep research needs more iterations (6+ phases with retries).
        is_deep_research = context.plan_graph.graph.get('research_mode') == 'deep_research'
        num_steps = sum(1 for n in context.plan_graph.nodes if n != "ROOT")
        max_iterations = max(self.max_steps * 3, 15) if is_deep_research else max(num_steps * 3, self.max_steps)
        iteration = 0
        
        # ===== COST THRESHOLD ENFORCEMENT =====
        from config.settings_loader import reload_settings
        settings = reload_settings()
        max_cost = settings.get("agent", {}).get("max_cost_per_run", 0.50)
        warn_cost = settings.get("agent", {}).get("warn_at_cost", 0.25)
        cost_warning_shown = False

        stall_counter = 0  # Counts consecutive iterations with no progress
        MAX_STALL = 20     # Break out after this many stalled iterations

        while not context.all_done():
            if context.stop_requested:
                console.print("[yellow]🛑 Aborting execution: Cleaning up nodes...[/yellow]")
                # Cleanup: Mark any 'running' nodes as 'stopped' to prevent zombie spinners in UI
                for n_id in context.plan_graph.nodes:
                    if context.plan_graph.nodes[n_id].get("status") == "running":
                        context.plan_graph.nodes[n_id]["status"] = "stopped"
                context._save_session()
                break

            # Get ready nodes (only returns pending nodes with all deps completed)
            ready_steps = context.get_ready_steps()

            if not ready_steps:
                # Check for running steps or waiting steps
                running_or_waiting = any(
                    context.plan_graph.nodes[n]['status'] in ['running', 'waiting_input']
                    for n in context.plan_graph.nodes
                )
                
                if not running_or_waiting:
                    # Cascade failures: mark pending steps blocked by non-completed predecessors
                    blocked_steps = []
                    non_complete_terminal = {'failed', 'skipped', 'cost_exceeded', 'stopped'}
                    for n in context.plan_graph.nodes:
                        if n == "ROOT":
                            continue
                        if context.plan_graph.nodes[n].get('status') == 'pending':
                            preds = list(context.plan_graph.predecessors(n))
                            if any(context.plan_graph.nodes[p].get('status') in non_complete_terminal for p in preds):
                                blocked_steps.append(n)

                    if blocked_steps:
                        for step_id in blocked_steps:
                            visualizer.mark_failed(step_id, "upstream dependency failed")
                            context.mark_failed(step_id, "Skipped: upstream dependency failed")
                            log_step(f"⏭️ Skipping {step_id}: upstream dependency failed", symbol="⏭️")
                        continue  # Re-check — cascaded failures may unblock or complete the graph

                    # Deadlock detection: pending nodes exist but none are blocked by
                    # failed predecessors — likely phantom nodes, cycles, or missing edges
                    remaining_pending = [
                        n for n in context.plan_graph.nodes
                        if n != "ROOT" and context.plan_graph.nodes[n].get('status') == 'pending'
                    ]
                    if remaining_pending:
                        log_step(f"Deadlock: {len(remaining_pending)} unreachable pending nodes — marking failed", symbol="⚠️")
                        for n_id in remaining_pending:
                            visualizer.mark_failed(n_id, "unreachable: no viable execution path")
                            context.mark_failed(n_id, "Unreachable: no viable execution path (possible cycle or missing dependency)")
                        continue  # Re-check all_done()

                    # Nothing pending, nothing running — we're done
                    break

                # Wait for progress (with stall detection)
                stall_counter += 1
                if stall_counter >= MAX_STALL:
                    log_error(f"🛑 DAG stalled: {MAX_STALL} iterations with no progress. Breaking out.")
                    break
                await asyncio.sleep(0.5)
                continue

            # Reset stall counter — we have work to do
            stall_counter = 0

            # Show current state (only when we found work to do)
            try:
                console.print(visualizer.get_layout())
            except Exception as e:
                console.print(f"[dim]Note: Could not refresh terminal UI: {e}[/dim]")

            # Mark running
            for step_id in ready_steps:
                visualizer.mark_running(step_id)
                context.mark_running(step_id)
            
            # ✅ EXECUTE AGENTS FOR REAL
            # Run each ready step concurrently (asyncio.gather)
            tasks = []
            for step_id in ready_steps:
                # Log step start with description
                step_data = context.get_step_data(step_id)
                desc = step_data.get("agent_prompt", step_data.get("description", "No description"))[:60]
                log_step(f"🔄 Starting {step_id} ({step_data['agent']}): {desc}...", symbol="🚀")

                tasks.append(self._track_task(self._execute_step(step_id, context)))

            results = await self._track_task(asyncio.gather(*tasks, return_exceptions=True))

            # Step-level retry configuration
            MAX_STEP_RETRIES = 2
            
            # Process results (with step-level retry)
            for step_id, result in zip(ready_steps, results):
                step_data = context.get_step_data(step_id)
                retry_count = step_data.get('_retry_count', 0)

                # Guard against None or unexpected result types
                if result is None or (not isinstance(result, (dict, Exception))):
                    # _execute_step returned something unexpected — treat as failure
                    visualizer.mark_failed(step_id, "No result returned")
                    context.mark_failed(step_id, "Step returned no result")
                    log_error(f"❌ {step_id}: _execute_step returned {type(result).__name__}")
                    continue

                # ✅ HANDLE AWAITING INPUT
                if isinstance(result, dict) and result.get("status") == "waiting_input":
                     visualizer.mark_waiting(step_id)
                     context.plan_graph.nodes[step_id]["status"] = "waiting_input"
                     # Preserve partial output
                     if "output" in result:
                         context.plan_graph.nodes[step_id]["output"] = result["output"]
                     context._save_session()
                     log_step(f"⏳ {step_id}: Waiting for user input...", symbol="⏳")
                     continue

                if isinstance(result, Exception):
                    # Check if we should retry this step
                    if retry_count < MAX_STEP_RETRIES:
                        step_data['_retry_count'] = retry_count + 1
                        context.plan_graph.nodes[step_id]['status'] = 'pending'  # Reset to pending for retry
                        log_step(f"🔄 Retrying {step_id} (attempt {retry_count + 1}/{MAX_STEP_RETRIES}): {str(result)}", symbol="🔄")
                    else:
                        visualizer.mark_failed(step_id, result)
                        context.mark_failed(step_id, str(result))
                        log_error(f"❌ Failed {step_id} after {MAX_STEP_RETRIES} retries: {str(result)}")
                elif result["success"]:
                    visualizer.mark_completed(step_id)
                    await context.mark_done(step_id, result["output"])
                    log_step(f"✅ Completed {step_id} ({step_data['agent']})", symbol="✅")
                    completed_now = sum(1 for n in context.plan_graph.nodes
                                        if n != "ROOT" and context.plan_graph.nodes[n].get("status") == "completed")
                    total_now = sum(1 for n in context.plan_graph.nodes if n != "ROOT")
                    await event_bus.publish("step_complete", "AgentLoop4", {
                        "step_id": step_id,
                        "agent": step_data["agent"],
                        "progress": f"{completed_now}/{total_now}",
                        "message": f"Completed {step_data['agent']} ({completed_now}/{total_now})"
                    })

                    # Auto-build source_index after RetrieverAgent completes
                    if step_data["agent"] == "RetrieverAgent":
                        self._auto_build_source_index(context)
                else:
                    # Agent returned failure - also retry
                    if retry_count < MAX_STEP_RETRIES:
                        step_data['_retry_count'] = retry_count + 1
                        context.plan_graph.nodes[step_id]['status'] = 'pending'
                        log_step(f"🔄 Retrying {step_id} (attempt {retry_count + 1}/{MAX_STEP_RETRIES}): {result['error']}", symbol="🔄")
                    else:
                        visualizer.mark_failed(step_id, result["error"])
                        context.mark_failed(step_id, result["error"])
                        log_error(f"❌ Failed {step_id} after {MAX_STEP_RETRIES} retries: {result['error']}")

            # ===== COST THRESHOLD CHECK =====
            accumulated_cost = sum(
                context.plan_graph.nodes[n].get('cost', 0) 
                for n in context.plan_graph.nodes
                if context.plan_graph.nodes[n].get('status') == 'completed'
            )
            
            # Warning threshold
            if not cost_warning_shown and accumulated_cost >= warn_cost:
                log_step(f"⚠️ Cost Warning: ${accumulated_cost:.4f} (threshold: ${warn_cost:.2f})", symbol="💰")
                cost_warning_shown = True
            
            # Hard stop threshold
            if accumulated_cost >= max_cost:
                log_error(f"🛑 Cost Exceeded: ${accumulated_cost:.4f} > ${max_cost:.2f}")
                context.plan_graph.graph['status'] = 'cost_exceeded'
                context.plan_graph.graph['final_cost'] = accumulated_cost
                break
                
            iteration += 1
            if iteration >= max_iterations:
                log_error(f"🛑 Max Iterations Reached: {iteration}/{max_iterations}")
                context.plan_graph.graph['status'] = 'failed'
                break

        # Final state: render layout and persist status
        console.print(visualizer.get_layout())

        # 🔧 CLEANUP: Mark any steps stuck in non-terminal states as failed
        for n_id in context.plan_graph.nodes:
            node_status = context.plan_graph.nodes[n_id].get("status")
            if node_status in ('pending', 'running'):
                context.mark_failed(n_id, f"Marked failed: loop ended with step in '{node_status}' state")
                log_step(f"🧹 Cleaned up {n_id}: {node_status} → failed", symbol="🧹")

        # Determine and save final status (stopped/failed/completed)
        if context.stop_requested:
             context.plan_graph.graph['status'] = 'stopped'
        elif any(context.plan_graph.nodes[n]['status'] == 'failed' for n in context.plan_graph.nodes):
             context.plan_graph.graph['status'] = 'failed'
        elif context.all_done():
             context.plan_graph.graph['status'] = 'completed'
        else:
             # Max iterations or stalled
             context.plan_graph.graph['status'] = 'failed'
        
        context._auto_save()
        
        if context.all_done():
            # 🧠 Save Episodic Memory (Skeleton)
            try:
                from core.episodic_memory import EpisodicMemory
                import networkx as nx
                mem = EpisodicMemory()
                graph_data = nx.node_link_data(context.plan_graph)
                session_data = {"graph": graph_data}
                await mem.save_episode(session_data)
            except Exception as e:
                print(f"⚠️ Failed to save episodic memory: {e}")

            console.print("🎉 All tasks completed!")

    async def _execute_steps_parallel(self, context, step_ids: list):
        """Execute steps in true parallel (deep research only).
        Each task processes its own result and publishes completion immediately."""
        if not step_ids:
            return

        log_step(f"⚡ Executing {len(step_ids)} agents in parallel: {step_ids}", symbol="⚡")

        for step_id in step_ids:
            context.mark_running(step_id)
            step_data = context.get_step_data(step_id)
            desc = step_data.get("description", "")[:60]
            log_step(f"🔄 Starting {step_id} ({step_data['agent']}): {desc}", symbol="🚀")

        MAX_STEP_RETRIES = 2

        async def _run_and_process(step_id):
            """Run step + process result + publish completion — all inside the parallel task."""
            step_data = context.get_step_data(step_id)
            retry_count = 0

            while retry_count <= MAX_STEP_RETRIES:
                try:
                    result = await self._execute_step(step_id, context, direct_search=True)
                except Exception as e:
                    result = e

                if isinstance(result, Exception):
                    retry_count += 1
                    if retry_count <= MAX_STEP_RETRIES:
                        context.plan_graph.nodes[step_id]['status'] = 'pending'
                        context.mark_running(step_id)
                        log_step(f"🔄 Retry {step_id} ({retry_count}/{MAX_STEP_RETRIES}): {result}", symbol="🔄")
                        continue
                    else:
                        context.mark_failed(step_id, str(result))
                        log_error(f"❌ Failed {step_id}: {result}")
                        return

                if result is None or not isinstance(result, dict):
                    context.mark_failed(step_id, "Step returned no result")
                    log_error(f"❌ {step_id}: returned {type(result).__name__}")
                    return

                if result.get("success"):
                    await context.mark_done(step_id, result["output"])
                    log_step(f"✅ Completed {step_id} ({step_data['agent']})", symbol="✅")
                    await event_bus.publish("step_complete", "AgentLoop4", {
                        "step_id": step_id,
                        "agent": step_data["agent"],
                        "message": f"Completed {step_data['agent']}"
                    })
                    return
                else:
                    retry_count += 1
                    if retry_count <= MAX_STEP_RETRIES:
                        context.plan_graph.nodes[step_id]['status'] = 'pending'
                        context.mark_running(step_id)
                        log_step(f"🔄 Retry {step_id} ({retry_count}/{MAX_STEP_RETRIES}): {result.get('error', 'Unknown')}", symbol="🔄")
                        continue
                    else:
                        context.mark_failed(step_id, result.get("error", "Unknown error"))
                        log_error(f"❌ Failed {step_id}: {result.get('error')}")
                        return

        tasks = {
            step_id: asyncio.create_task(_run_and_process(step_id))
            for step_id in step_ids
        }
        for t in tasks.values():
            self._tasks.add(t)

        await asyncio.gather(*tasks.values(), return_exceptions=True)

        for t in tasks.values():
            self._tasks.discard(t)

        # Build source_index once after ALL retrievers complete
        self._auto_build_source_index(context)

    async def _execute_step(self, step_id, context, direct_search=False):
        """Execute a single step with call_self support"""
        # 📡 EMIT PROGRESS EVENT — count total and completed steps for progress
        total_steps = sum(1 for n in context.plan_graph.nodes if n != "ROOT")
        completed_steps = sum(1 for n in context.plan_graph.nodes
                              if n != "ROOT" and context.plan_graph.nodes[n].get("status") == "completed")
        step_data = context.get_step_data(step_id)
        agent_type = step_data["agent"]
        desc = step_data.get("description", "")[:80]

        # Validate agent type exists in registry
        from core.registry import AgentRegistry
        if not AgentRegistry.get(agent_type):
            error_msg = f"Unknown agent type: {agent_type} (Not found in Registry). Available: {', '.join(AgentRegistry.list_agents().keys())}"
            log_error(error_msg)
            return {"success": False, "error": error_msg}

        await event_bus.publish("step_start", "AgentLoop4", {
            "step_id": step_id,
            "agent": agent_type,
            "description": desc,
            "progress": f"{completed_steps + 1}/{total_steps}",
            "message": f"Running {agent_type} ({completed_steps + 1}/{total_steps}): {desc}"
        })
        
        # Get inputs from NetworkX graph
        inputs = context.get_inputs(step_data.get("reads", []))

        # Auto-inject source_index for SummarizerAgent and FormatterAgent
        if agent_type in ("SummarizerAgent", "FormatterAgent"):
            gs = context.plan_graph.graph.get('globals_schema', {})
            if "source_index" in gs and "source_index" not in inputs:
                inputs["source_index"] = gs["source_index"]

        # 🔧 HELPER FUNCTION: Build agent input (consistent for both iterations)
        def build_agent_input(instruction=None, previous_output=None, iteration_context=None):
            # Base payload for all agents
            payload = {
                "step_id": step_id,
                "agent_prompt": instruction or step_data.get("agent_prompt", step_data["description"]),
                "reads": step_data.get("reads", []),
                "writes": step_data.get("writes", []),
                "inputs": inputs,
                "original_query": context.plan_graph.graph['original_query'],
                "session_context": {
                    "session_id": context.plan_graph.graph['session_id'],
                    "created_at": context.plan_graph.graph['created_at'],
                    "file_manifest": context.plan_graph.graph['file_manifest'],
                    "memory_context": getattr(context, 'memory_context', None) # 🧠 Universal Injection
                },
                **({"previous_output": previous_output} if previous_output else {}),
                **({"iteration_context": iteration_context} if iteration_context else {})
            }
            
            # Formatter-specific additions
            if agent_type == "FormatterAgent":
                payload["all_globals_schema"] = context.plan_graph.graph['globals_schema'].copy()
                
            return payload

            max_turns = 15
            current_input = build_agent_input()
            iterations_data = []

            # ReAct loop: agent can call tools, call_self, or produce final output
            for turn in range(1, max_turns + 1):
                with agent_iteration_span(step_id, agent_type, session_id_val, turn, max_turns) as iter_span:
                    log_step(f"🔄 {agent_type} Iteration {turn}/{max_turns}", symbol="🔄")

                    # Run agent step (with retries for transient failures)
                    async def run_agent_step():
                        return await self.agent_runner.run_agent(agent_type, current_input)

                    def on_retry(attempt):
                        iter_span.set_attribute("retry_attempt", attempt)
                        iter_span.set_attribute("is_retry", True)

                    try:
                        result = await retry_with_backoff(run_agent_step, on_retry=on_retry)
                    except Exception as e:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                        return {"success": False, "error": f"Agent failed after retries: {str(e)}"}

                    if not result["success"]:
                        iter_span.set_attribute("trigger", "error")
                        return result

                    output = result["output"]

                    # Clarification requested - pause for user input
                    if output.get("clarificationMessage"):
                        iter_span.set_attribute("trigger", "clarification")
                        return {
                            "success": True,
                            "status": "waiting_input",
                            "output": output
                        }
        # Execute with ReAct Loop (Max 15 turns)
        max_turns = 15
        current_input = build_agent_input()
        iterations_data = []
        
        for turn in range(1, max_turns + 1):
            log_step(f"🔄 {agent_type} Iteration {turn}/{max_turns}", symbol="🔄")
            
            # Run Agent (with retry for transient failures like rate limits)
            async def run_agent_step():
                return await self.agent_runner.run_agent(agent_type, current_input)
            
            try:
                result = await retry_with_backoff(run_agent_step)
            except Exception as e:
                # All retries exhausted, return failure
                return {"success": False, "error": f"Agent failed after retries: {str(e)}"}
            
            if not result["success"]:
                return result
            
            output = result["output"]

            # 🔧 ROBUSTNESS: Ensure output is a dict (Gemma may return a list)
            if isinstance(output, list):
                if len(output) > 0 and isinstance(output[0], dict):
                    output = output[0]
                else:
                    log_step(f"⚠️ {agent_type} returned a list instead of dict, wrapping", symbol="⚠️")
                    output = {"raw_output": output}
            elif not isinstance(output, dict):
                output = {"raw_output": str(output)}

            # ✅ CHECK FOR CLARIFICATION REQUEST (HALT)
            if output.get("clarificationMessage"):
                 return {
                    "success": True, 
                    "status": "waiting_input", 
                    "output": output
                 }

                    iterations_data.append({"iteration": turn, "output": output})

                    if context.stop_requested:
                        iter_span.set_attribute("trigger", "stopped")
                        log_step(f"🛑 {agent_type}: Stop requested, aborting iteration {turn}", symbol="🛑")
                        return {"success": False, "error": "Stop requested"}

                    step_data = context.get_step_data(step_id)
                    step_data['iterations'] = iterations_data

                    # 1. Check for 'call_tool' (ReAct)
                    if output.get("call_tool"):
                        iter_span.set_attribute("trigger", "tool_call")
                        tool_call = output["call_tool"]
                        # 🔧 ROBUSTNESS: tool_call might be a list (Gemma quirk)
                if isinstance(tool_call, list) and len(tool_call) > 0:
                    tool_call = tool_call[0] if isinstance(tool_call[0], dict) else {"name": str(tool_call[0])}
                elif not isinstance(tool_call, dict):
                    tool_call = {"name": str(tool_call)}
                tool_name = tool_call.get("name")
                        tool_args = tool_call.get("arguments", {})
                # 🔧 ROBUSTNESS: Ensure tool_args is a dict (Gemma may output a list)
                if isinstance(tool_args, list):
                    log_step(f"⚠️ Tool args is a list, converting to dict", symbol="⚠️")
                    tool_args = {f"arg_{i}": v for i, v in enumerate(tool_args)}
                elif not isinstance(tool_args, dict):
                    tool_args = {"value": tool_args}

                        log_step(f"🛠️ Executing Tool: {tool_name}", payload=tool_args, symbol="⚙️")
                await event_bus.publish("tool_call", "AgentLoop4", {
                    "step_id": step_id,
                    "agent": agent_type,
                    "tool_name": tool_name,
                    "message": f"{agent_type} calling {tool_name}..."
                })

                        tool_executed = False
                        skill_tool_result = None

                        # Try local skill tools first, then MCP route
                        try:
                            from core.registry import AgentRegistry
                            from shared.state import get_skill_manager

                            agent_config = AgentRegistry.get(agent_type)
                            skill_mgr = get_skill_manager()

                            if agent_config and "skills" in agent_config:
                                possible_skills = agent_config["skills"]
                                for skill_name in possible_skills:
                                    skill = skill_mgr.get_skill(skill_name)
                                    if skill:
                                        for tool in skill.get_tools():
                                            if getattr(tool, 'name', None) == tool_name:
                                                log_step(f"🧩 Executing Local Skill Tool: {tool_name}", symbol="🧩")
                                                if asyncio.iscoroutinefunction(tool.func):
                                                    skill_tool_result = await tool.func(**tool_args)
                                                else:
                                                    skill_tool_result = tool.func(**tool_args)
                                                tool_executed = True
                                                break
                                    if tool_executed:
                                        break

                        except Exception as e:
                            log_error(f"Local Skill Tool Execution Failed: {e}")
                            tool_executed = True
                            skill_tool_result = f"Error executing local skill tool: {str(e)}"

                        # Execute tool via MCP when not a local skill
                        if not tool_executed:
                            try:
                                mcp_result = await self.multi_mcp.route_tool_call(tool_name, tool_args)
                                if hasattr(mcp_result, 'content'):
                                    if isinstance(mcp_result.content, list):
                                        skill_tool_result = "\n".join([str(item.text) for item in mcp_result.content if hasattr(item, "text")])
                                    else:
                                        skill_tool_result = str(mcp_result.content)
                                else:
                                    skill_tool_result = str(mcp_result)
                            except Exception as e:
                                log_error(f"Tool Execution Failed: {e}")
                                current_input = build_agent_input(
                                    instruction="The tool execution failed. Try a different approach or tool.",
                                    previous_output=output,
                                    iteration_context={"tool_result": f"Error: {str(e)}"}
                                )
                                continue

                        # Feed tool result back to agent for next iteration
                        result_str = str(skill_tool_result)
                        iterations_data[-1]["tool_result"] = result_str
                        log_step(f"✅ Tool Result", payload={"result_preview": result_str[:200] + "..."}, symbol="🔌")
                        instruction = output.get("thought", "Use the tool result to generate the final output.")
                        if turn == max_turns - 1:
                            instruction += " \n\n⚠️ WARNING: This is your FINAL turn. You MUST provide the final 'output' now. Do not call any more tools. Summarize what you have."
                        current_input = build_agent_input(
                            instruction=instruction,
                            previous_output=output,
                            iteration_context={"tool_result": result_str}
                        )
                        continue
                # 1b. Direct search bypass (parallel deep research)
                if not tool_executed and direct_search and tool_name == "search_web_with_text_content":
                    try:
                        query = tool_args.get("string", "")
                        num_results = tool_args.get("integer", 5)
                        log_step(f"⚡ Direct search (parallel): {query[:60]}...", symbol="⚡")

                        total_sources = min(max(num_results, 1), 20)
                        progress_task = asyncio.create_task(self._emit_source_progress_helper(step_id, total_sources))

                        skill_tool_result = await self._direct_web_search(query, num_results)

                        if progress_task and not progress_task.done():
                            progress_task.cancel()
                        tool_executed = True
                    except Exception as e:
                        log_error(f"Direct search failed, falling back to MCP: {e}")
                        # tool_executed stays False → falls through to MCP

                # 1c. Fallback to MultiMCP
                if not tool_executed:
                    try:
                        # Stream per-source progress for search tools
                        progress_task = None
                        if tool_name == "search_web_with_text_content":
                            total_sources = min(max(tool_args.get("integer", 5), 1), 20)
                            async def _emit_source_progress():
                                # Sources extract concurrently (~1-8s each).
                                # Emit progress ticks so the UI shows "Reading source N/M..."
                                interval = max(0.6, 8.0 / total_sources)
                                for i in range(1, total_sources + 1):
                                    await asyncio.sleep(interval)
                                    await event_bus.publish("source_progress", "AgentLoop4", {
                                        "step_id": step_id,
                                        "current": i,
                                        "total": total_sources,
                                        "message": f"Reading source {i}/{total_sources}..."
                                    })
                            progress_task = asyncio.create_task(_emit_source_progress())

                        # Execute tool via MultiMCP
                        mcp_result = await self.multi_mcp.route_tool_call(tool_name, tool_args)

                        # Cancel progress emitter once tool completes
                        if progress_task and not progress_task.done():
                            progress_task.cancel()

                        # Serialize result content
                        if hasattr(mcp_result, 'content'):
                            if isinstance(mcp_result.content, list):
                                skill_tool_result = "\n".join([str(item.text) for item in mcp_result.content if hasattr(item, "text")])
                            else:
                                skill_tool_result = str(mcp_result.content)
                        else:
                            skill_tool_result = str(mcp_result)

                    except Exception as e:
                        if progress_task and not progress_task.done():
                            progress_task.cancel()
                        log_error(f"Tool Execution Failed: {e}")
                        # Feed error back to agent
                        current_input = build_agent_input(
                            instruction="The tool execution failed. Try a different approach or tool.",
                            previous_output=output,
                            iteration_context={"tool_result": f"Error: {str(e)}"}
                        )
                        continue
                
                # Common success path
                result_str = str(skill_tool_result)

                # ✅ SAVE RESULT TO HISTORY
                iterations_data[-1]["tool_result"] = result_str

                # 📡 EMIT TOOL RESULT EVENT with source count
                source_count = 0
                try:
                    import json as _json
                    parsed = _json.loads(result_str) if result_str.startswith("[") else None
                    if isinstance(parsed, list):
                        source_count = len(parsed)
                except Exception:
                    pass
                await event_bus.publish("tool_result", "AgentLoop4", {
                    "step_id": step_id,
                    "tool_name": tool_name,
                    "source_count": source_count,
                    "message": f"Processed {source_count} sources from {tool_name}" if source_count else f"Tool {tool_name} completed"
                })

                # Log result (truncated)
                log_step(f"✅ Tool Result", payload={"result_preview": result_str[:200] + "..."}, symbol="🔌")
                
                # Prepare input for next iteration
                instruction = output.get("thought", "Use the tool result to generate the final output.")
                if turn == max_turns - 1:
                        instruction += " \n\n⚠️ WARNING: This is your FINAL turn. You MUST provide the final 'output' now. Do not call any more tools. Summarize what you have."

                current_input = build_agent_input(
                    instruction=instruction,
                    previous_output=output,
                    iteration_context={"tool_result": result_str}
                )
                continue # Loop to next turn

                    # 2. Check for call_self (Legacy/Advanced recursion)
                    elif output.get("call_self"):
                        iter_span.set_attribute("trigger", "call_self")
                        if context._has_executable_code(output):
                            execution_result = await context._auto_execute_code(step_id, output)
                            iterations_data[-1]["execution_result"] = execution_result
                            if execution_result.get("status") == "success":
                                execution_data = execution_result.get("result", {})
                                inputs = {**inputs, **execution_data}
                        current_input = build_agent_input(
                            instruction=output.get("next_instruction", "Continue the task"),
                            previous_output=output,
                            iteration_context=output.get("iteration_context", {})
                        )
                        continue
            # 2. Check for call_self (Legacy/Advanced recursion)
            elif output.get("call_self"):
                # Handle code execution if needed
                if context._has_executable_code(output):
                    execution_result = await context._auto_execute_code(step_id, output)
                    
                    # ✅ SAVE RESULT TO HISTORY
                    iterations_data[-1]["execution_result"] = execution_result

                    if execution_result.get("status") == "success":
                        execution_data = execution_result.get("result", {})
                        if isinstance(execution_data, dict):
                            inputs = {**inputs, **execution_data}  # Update inputs for iteration 2
                        else:
                            inputs["execution_result"] = execution_data
                
                # Prepare input for next iteration
                current_input = build_agent_input(
                    instruction=output.get("next_instruction", "Continue the task"),
                    previous_output=output,
                    iteration_context=output.get("iteration_context", {})
                )
                continue

                    # 3. Final output (no tool/self call) - execute code if present, then return
                    else:
                        iter_span.set_attribute("trigger", "final")
                        if context.stop_requested:
                            return {"success": False, "error": "Stop requested"}
                        if context._has_executable_code(output):
                            execution_result = await context._auto_execute_code(step_id, output)
                            iterations_data[-1]["execution_result"] = execution_result
                            # Merge so mark_done skips re-execution (avoids duplicate code.execution span)
                            output = context._merge_execution_results(output, execution_result)
                        return {"success": True, "output": output}

            log_error(f"Max iterations ({max_turns}) reached for {step_id}. Returning last output (incomplete).")
            # 3. Success (No tool call, just output) - Execute code for final iteration
            else:
                # ✅ LAST-SECOND STOP CHECK
                if context.stop_requested:
                    return {"success": False, "error": "Stop requested"}

                # Execute code if present and merge into output
                if context._has_executable_code(output):
                    execution_result = await context._auto_execute_code(step_id, output)
                    iterations_data[-1]["execution_result"] = execution_result
                    # Merge execution results into the output and flag as already executed
                    # so mark_done doesn't re-execute
                    output = context._merge_execution_results(output, execution_result)
                    output["_code_already_executed"] = True
                    result = {**result, "output": output}
                return result
        
        # If loop finishes without returning (max turns reached): Return PARTIAL SUCCESS to allow graph continuation
        log_error(f"Max iterations ({max_turns}) reached for {step_id}. Returning last output (incomplete).")
        last_output = iterations_data[-1]["output"] if iterations_data else {"error": "No output produced"}
        # Ensure it has a valid structure if possible, or just pass it through
        return {"success": True, "output": last_output}

    async def _handle_failures(self, context):
        """Handle failures via mid-session replanning"""
        # TODO: Implement mid-session replanning with PlannerAgent
        log_error("Mid-session replanning not yet implemented")
