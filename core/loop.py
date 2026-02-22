# flow.py – 100% NetworkX Graph-First (No agentSession)

import networkx as nx
import asyncio
import time
from memory.context import ExecutionContextManager
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
    retryable_errors: tuple = None
):
    """
    Retry an async function with exponential backoff.
    
    Args:
        async_func: Async callable to execute
        max_retries: Maximum retry attempts (default: 3)
        base_delay: Initial delay in seconds (default: 1.0)
        retryable_errors: Tuple of exception types to retry on
        
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
            
            # 3. Execute DAG
            return await self._execute_dag(self.context)
            
        except Exception as e:
            log_error(f"Failed to resume session: {e}")
            raise

    async def run(self, query, file_manifest, globals_schema, uploaded_files, session_id=None, memory_context=None, research_mode="standard", focus_mode=None):
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
            self.context.memory_context = memory_context # Store for retrieval
            # Inject multi_mcp immediately
            self.context.multi_mcp = self.multi_mcp
            self.context.plan_graph.graph['globals_schema'].update(globals_schema)
            self.context.plan_graph.graph['research_mode'] = research_mode
            self.context.plan_graph.graph['focus_mode'] = focus_mode
            self.context._save_session()
            log_step("✅ Session initialized with Query processing", symbol="🌱")
        except Exception as e:
            print(f"❌ ERROR initializing context: {e}")
            raise


        # Phase 1: File Profiling (if files exist)
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
                
                async def run_planner():
                    # 🧠 Enable System 2 Reasoning for the Planner
                    # This ensures the plan is Verified and Refined before execution
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
                        use_system2=True
                    )
                
                plan_result = await self._track_task(retry_with_backoff(run_planner))

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
                    
                    # Insert clarification node at beginning
                    plan_result["output"]["plan_graph"]["nodes"].insert(0, clarification_node)
                    
                    # Add edge from ROOT to clarification, and clarification to first step
                    plan_result["output"]["plan_graph"]["edges"].insert(0, {
                        "source": "T000_AutoClarify",
                        "target": first_step
                    })
                    
                    # 🔧 CRITICAL FIX: Wire clarification output into the downstream node's reads
                    # Find the first_step node and add clarification_write_key to its reads
                    for node in plan_result["output"]["plan_graph"]["nodes"]:
                        if node.get("id") == first_step:
                            if "reads" not in node:
                                node["reads"] = []
                            if clarification_write_key not in node["reads"]:
                                node["reads"].append(clarification_write_key)
                                log_step(f"Wired {clarification_write_key} into {first_step}'s reads", symbol="🔗")
                            break
                    
                    # Update next_step_id to start with clarification
                    plan_result["output"]["next_step_id"] = "T000_AutoClarify"
                    
                    log_step(f"Injected ClarificationAgent before {first_step}", symbol="➕")
                elif has_clarification_agent:
                    log_step(f"Planner already added ClarificationAgent, skipping auto-injection", symbol="ℹ️")
                
                # ✅ Mark Query/Planner as Done
                self.context.plan_graph.nodes["Query"]["output"] = plan_result["output"]
                self.context.plan_graph.nodes["Query"]["status"] = "completed"
                self.context.plan_graph.nodes["Query"]["end_time"] = datetime.utcnow().isoformat()
                
                # 🟢 PHASE 3: EXPAND GRAPH
                # Merge the new plan into our existing context
                new_plan_graph = plan_result["output"]["plan_graph"]
                self._merge_plan_into_context(new_plan_graph)

                try:
                    # Phase 4: Execute DAG
                    await self._track_task(self._execute_dag(self.context))

                    if self.context.stop_requested:
                        break

                    # Phase 5: Check for Adaptive Re-Planning (Dead End Discovery)
                    if self._should_replan():
                        log_step("♻️ Adaptive Re-planning: Clarification resolved, formulating next steps...", symbol="🔄")
                        # Reactivate Query node for UI
                        self.context.plan_graph.nodes["Query"]["status"] = "running"
                        self.context._save_session()
                        continue
                    else:
                        # No more work or re-planning needed
                        return self.context

                except (Exception, asyncio.CancelledError) as e:
                    if isinstance(e, asyncio.CancelledError) or self.context.stop_requested:
                        log_step("🛑 Execution interrupted/stopped.", symbol="🛑")
                        break
                    print(f"❌ ERROR during execution: {e}")
                    import traceback
                    traceback.print_exc()
                    raise
        except (Exception, asyncio.CancelledError) as e:
            if self.context:
                # Mark ANY running/pending node as stopped/failed to stop spinners
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

    def _merge_plan_into_context(self, new_plan_graph):
        """Merge the planned nodes into the existing bootstrap context"""
        new_nodes = new_plan_graph.get("nodes", [])
        new_edges = new_plan_graph.get("edges", [])
        
        # Track which new nodes have incoming edges to detect orphans
        nodes_with_incoming_edges = set()

        # Add new nodes
        for node in new_nodes:
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
            
        # Add new edges, redirecting ROOT -> First Step to Query -> First Step
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

            self.context.plan_graph.add_edge(source, target)
            nodes_with_incoming_edges.add(target)
        
        # 🛡️ AUTO-CONNECT: If a new node has NO incoming edges, connect it to "Query"
        # This fixes cases where PlannerAgent returns nodes but forgets the edges
        for node in new_nodes:
            if node["id"] not in nodes_with_incoming_edges:
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
        # Deep research needs more iterations (6+ phases with retries)
        is_deep_research = context.plan_graph.graph.get('research_mode') == 'deep_research'
        max_iterations = max(self.max_steps * 3, 15) if is_deep_research else self.max_steps
        iteration = 0
        
        # ===== COST THRESHOLD ENFORCEMENT =====
        from config.settings_loader import reload_settings
        settings = reload_settings()
        max_cost = settings.get("agent", {}).get("max_cost_per_run", 0.50)
        warn_cost = settings.get("agent", {}).get("warn_at_cost", 0.25)
        cost_warning_shown = False

        while not context.all_done():
            if context.stop_requested:
                console.print("[yellow]🛑 Aborting execution: Cleaning up nodes...[/yellow]")
                # Cleanup: Mark any 'running' nodes as 'stopped' to prevent zombie spinners in UI
                for n_id in context.plan_graph.nodes:
                    if context.plan_graph.nodes[n_id].get("status") == "running":
                        context.plan_graph.nodes[n_id]["status"] = "stopped"
                context._save_session()
                break
            
            # Get ready nodes
            ready_steps = context.get_ready_steps()
            
            # 🛡️ DEFENSIVE: Filter out steps that are not pending (prevents loops)
            ready_steps = [s for s in ready_steps if context.plan_graph.nodes[s]["status"] == "pending"]
            
            if not ready_steps:
                # Check for running steps or waiting steps
                running_or_waiting = any(
                    context.plan_graph.nodes[n]['status'] in ['running', 'waiting_input']
                    for n in context.plan_graph.nodes
                )
                
                if not running_or_waiting:
                    # If no ready steps, and nothing is running/waiting, and we aren't "all_done" (maybe orphans?)
                    # Check if everything is completed or skipped
                    is_complete = all(
                        context.plan_graph.nodes[n]['status'] in ['completed', 'skipped', 'cost_exceeded']
                        for n in context.plan_graph.nodes
                        if n != "ROOT"
                    )
                    if is_complete:
                        break
                
                # Wait for progress
                await asyncio.sleep(0.5)
                continue

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
            tasks = []
            for step_id in ready_steps:
                # Log step start with description
                step_data = context.get_step_data(step_id)
                desc = step_data.get("agent_prompt", step_data.get("description", "No description"))[:60]
                log_step(f"🔄 Starting {step_id} ({step_data['agent']}): {desc}...", symbol="🚀")
                
                visualizer.mark_running(step_id)
                context.mark_running(step_id)
                tasks.append(self._track_task(self._execute_step(step_id, context)))

            results = await self._track_task(asyncio.gather(*tasks, return_exceptions=True))

            # Step-level retry configuration
            MAX_STEP_RETRIES = 2
            
            # Process results (with step-level retry)
            for step_id, result in zip(ready_steps, results):
                step_data = context.get_step_data(step_id)
                retry_count = step_data.get('_retry_count', 0)
                
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

        # Final state
        console.print(visualizer.get_layout())

        # 🔧 CLEANUP: Mark any steps stuck in non-terminal states as failed
        for n_id in context.plan_graph.nodes:
            node_status = context.plan_graph.nodes[n_id].get("status")
            if node_status in ('pending', 'running'):
                context.mark_failed(n_id, f"Marked failed: loop ended with step in '{node_status}' state")
                log_step(f"🧹 Cleaned up {n_id}: {node_status} → failed", symbol="🧹")

        # Determine and save final status
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

    async def _execute_step(self, step_id, context):
        """Execute a single step with call_self support"""
        # 📡 EMIT EVENT
        await event_bus.publish("step_start", "AgentLoop4", {"step_id": step_id})
        step_data = context.get_step_data(step_id)
        agent_type = step_data["agent"]
        
        # Get inputs from NetworkX graph
        inputs = context.get_inputs(step_data.get("reads", []))
        
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
            
            # ✅ IMMEDIATE STOP CHECK (Between turns)
            if context.stop_requested:
                log_step(f"🛑 {agent_type}: Stop requested, aborting iteration {turn}", symbol="🛑")
                return {"success": False, "error": "Stop requested"}

            # Update step data with iterations so far
            step_data = context.get_step_data(step_id)
            step_data['iterations'] = iterations_data
            
                # 1. Check for 'call_tool' (ReAct)
            if output.get("call_tool"):
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
                
                # 1a. Try LOCAL SKILL TOOLS first
                tool_executed = False
                skill_tool_result = None
                
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
                            if tool_executed: break

                except Exception as e:
                    log_error(f"Local Skill Tool Execution Failed: {e}")
                    tool_executed = True # Failed but found
                    skill_tool_result = f"Error executing local skill tool: {str(e)}"

                # 1b. Fallback to MultiMCP
                if not tool_executed:
                    try:
                        # Execute tool via MultiMCP
                        mcp_result = await self.multi_mcp.route_tool_call(tool_name, tool_args)
                        
                        # Serialize result content
                        if hasattr(mcp_result, 'content'):
                            if isinstance(mcp_result.content, list):
                                skill_tool_result = "\n".join([str(item.text) for item in mcp_result.content if hasattr(item, "text")])
                            else:
                                skill_tool_result = str(mcp_result.content)
                        else:
                            skill_tool_result = str(mcp_result)
                            
                    except Exception as e:
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

            # 3. Success (No tool call, just output) - Execute code for final iteration
            else:
                # ✅ LAST-SECOND STOP CHECK
                if context.stop_requested:
                    return {"success": False, "error": "Stop requested"}
                    
                # Execute code if present and save to iterations_data (same as call_self path)
                if context._has_executable_code(output):
                    execution_result = await context._auto_execute_code(step_id, output)
                    iterations_data[-1]["execution_result"] = execution_result
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
