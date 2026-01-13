# flow.py – 100% NetworkX Graph-First (No agentSession)

import networkx as nx
import asyncio
from memory.context import ExecutionContextManager
from agents.base_agent import AgentRunner
from core.utils import log_step, log_error
from core.model_manager import ModelManager
from ui.visualizer import ExecutionVisualizer
from rich.live import Live
from rich.console import Console
from datetime import datetime

class AgentLoop4:
    def __init__(self, multi_mcp, strategy="conservative"):
        self.multi_mcp = multi_mcp
        self.strategy = strategy
        self.agent_runner = AgentRunner(multi_mcp)
        self.context = None  # Reference for external stopping

    def stop(self):
        """Request execution stop"""
        if self.context:
            self.context.stop()

    async def run(self, query, file_manifest, globals_schema, uploaded_files, session_id=None, memory_context=None):
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
            self.context._save_session()
            log_step("✅ Session initialized with Query processing", symbol="🌱")
        except Exception as e:
            print(f"❌ ERROR initializing context: {e}")
            raise

        # Phase 1: File Profiling (if files exist)
        file_profiles = {}
        if uploaded_files:
            file_result = await self.agent_runner.run_agent(
                "DistillerAgent",
                {
                    "task": "profile_files",
                    "files": uploaded_files,
                    "instruction": "Profile and summarize each file's structure, columns, content type",
                    "writes": ["file_profiles"]
                }
            )
            if file_result["success"]:
                file_profiles = file_result["output"]
                self.context.set_file_profiles(file_profiles)

        # Phase 2: Planning with AgentRunner
        # Note: The "Query" node is already 'running' in our bootstrap context
        plan_result = await self.agent_runner.run_agent(
            "PlannerAgent",
            {
                "original_query": query,
                "planning_strategy": self.strategy,
                "globals_schema": globals_schema,
                "file_manifest": file_manifest,
                "file_profiles": file_profiles,
                "memory_context": memory_context
            }
        )

        if not plan_result["success"]:
            self.context.mark_failed("Query", plan_result['error'])
            raise RuntimeError(f"Planning failed: {plan_result['error']}")

        if 'plan_graph' not in plan_result['output']:
            self.context.mark_failed("Query", "Output missing plan_graph")
            raise RuntimeError(f"PlannerAgent output missing 'plan_graph' key.")
        
        # ✅ Mark Query/Planner as Done
        self.context.plan_graph.nodes["Query"]["output"] = plan_result["output"]
        self.context.plan_graph.nodes["Query"]["status"] = "completed"
        self.context.plan_graph.nodes["Query"]["end_time"] = datetime.utcnow().isoformat()
        
        # 🟢 PHASE 3: EXPAND GRAPH
        # Merge the new plan into our existing context
        new_plan_graph = plan_result["output"]["plan_graph"]
        self._merge_plan_into_context(new_plan_graph)

        try:
            # Phase 4: Execute DAG with visualization
            await self._execute_dag(self.context)

            # Phase 5: Return the CONTEXT OBJECT
            return self.context

        except Exception as e:
            print(f"❌ ERROR during execution: {e}")
            import traceback
            traceback.print_exc()
            raise

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
                
            self.context.plan_graph.add_node(node["id"], **node_data)
            
        # Add new edges, redirecting ROOT -> First Step to Query -> First Step
        for edge in new_edges:
            source = edge["source"]
            target = edge["target"]
            
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
        max_iterations = 20
        iteration = 0

        while not context.all_done() and iteration < max_iterations:
            iteration += 1
            
            if context.stop_requested:
                console.print("[yellow]🛑 Execution stopped by user[/yellow]")
                break
            
            # Show current state
            console.print(visualizer.get_layout())
            
            # Get ready nodes
            ready_steps = context.get_ready_steps()
            
            if not ready_steps:
                # Check for failures
                has_failures = any(
                    context.plan_graph.nodes[n]['status'] == 'failed' 
                    for n in context.plan_graph.nodes
                )
                if has_failures:
                    break
                await asyncio.sleep(0.3)
                continue

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
                tasks.append(self._execute_step(step_id, context))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for step_id, result in zip(ready_steps, results):
                step_data = context.get_step_data(step_id)
                if isinstance(result, Exception):
                    visualizer.mark_failed(step_id, result)
                    context.mark_failed(step_id, str(result))
                    log_error(f"❌ Failed {step_id}: {str(result)}")
                elif result["success"]:
                    visualizer.mark_completed(step_id)
                    await context.mark_done(step_id, result["output"])
                    log_step(f"✅ Completed {step_id} ({step_data['agent']})", symbol="✅")
                else:
                    visualizer.mark_failed(step_id, result["error"])
                    context.mark_failed(step_id, result["error"])
                    log_error(f"❌ Failed {step_id}: {result['error']}")

        # Final state
        console.print(visualizer.get_layout())
        
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
            console.print("🎉 All tasks completed!")

    async def _execute_step(self, step_id, context):
        """Execute a single step with call_self support"""
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
            
            # Run Agent
            result = await self.agent_runner.run_agent(agent_type, current_input)
            
            if not result["success"]:
                return result
            
            output = result["output"]
            iterations_data.append({"iteration": turn, "output": output})
            
            # Update step data with iterations so far
            step_data = context.get_step_data(step_id)
            step_data['iterations'] = iterations_data
            
            # 1. Check for 'call_tool' (ReAct)
            if output.get("call_tool"):
                tool_call = output["call_tool"]
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("arguments", {})
                
                log_step(f"🛠️ Executing Tool: {tool_name}", payload=tool_args, symbol="⚙️")
                
                try:
                    # Execute tool via MultiMCP
                    tool_result = await self.multi_mcp.route_tool_call(tool_name, tool_args)
                    
                    # Serialize result content
                    if isinstance(tool_result.content, list):
                        result_str = "\n".join([str(item.text) for item in tool_result.content if hasattr(item, "text")])
                    else:
                        result_str = str(tool_result.content)

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

                except Exception as e:
                    log_error(f"Tool Execution Failed: {e}")
                    # Feed error back to agent
                    current_input = build_agent_input(
                        instruction="The tool execution failed. Try a different approach or tool.",
                        previous_output=output,
                        iteration_context={"tool_result": f"Error: {str(e)}"}
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
                        inputs = {**inputs, **execution_data}  # Update inputs for iteration 2
                
                # Prepare input for next iteration
                current_input = build_agent_input(
                    instruction=output.get("next_instruction", "Continue the task"),
                    previous_output=output,
                    iteration_context=output.get("iteration_context", {})
                )
                continue

            # 3. Success (No tool call, just output) - Execute code for final iteration
            else:
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
