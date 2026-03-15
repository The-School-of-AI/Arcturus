import json
from typing import Dict, List, Any, Optional
from core.utils import log_step, log_error

from memory.episodic import MEMORY_DIR, search_episodes, get_recent_episodes
from memory.space_constants import SPACE_ID_GLOBAL

class MemorySkeletonizer:
    """
    Compresses full execution graphs into lightweight 'Skeletons' (Recipes).
    Removes heavy payloads (HTML, huge text) but preserves Logic (Prompts, Tool Calls).
    """
    @staticmethod
    def skeletonize(session_data: Dict) -> Dict:
        # Robust extraction: 'nodes' might be at root or inside 'graph' wrapper
        graph_data = session_data.get("graph", session_data)
        
        # If 'graph' points to attributes (like in the file 1770375024), we might need to look at root
        if "nodes" in session_data:
            nodes = session_data["nodes"]
            edges = session_data.get("edges", session_data.get("links", []))
            # Metadata might be in 'graph' key
            metadata = session_data.get("graph", {})
        else:
            # Standard Wrapper Case
            nodes = graph_data.get("nodes", [])
            edges = graph_data.get("edges", graph_data.get("links", []))
            metadata = graph_data
            
        skeleton = {
            "id": metadata.get("session_id"),
            "original_query": metadata.get("original_query"),
            "outcome": metadata.get("status"),
            "final_cost": metadata.get("final_cost"),
            "nodes": [],
            "edges": edges 
        }
        
        for node in nodes:
            # 1. Base lightweight info
            s_node = {
                "id": node.get("id"),
                "agent": node.get("agent"),
                "task_goal": node.get("description"), # Renamed for clarity
                "status": node.get("status"),
                "error": node.get("error"),
                "io_signature": {
                    "reads": node.get("reads", []),
                    "writes": node.get("writes", [])
                }
            }
            
            # 2. Extract Logic (Agent Prompt & Thought) - The "Recipe"
            if "agent_prompt" in node:
                s_node["instruction"] = node["agent_prompt"]
            
            # Capture Planner Logic (Ambiguity & Confidence)
            if node.get("agent") == "PlannerAgent":
                output = node.get("output", {})
                if isinstance(output, dict):
                    if "ambiguity_notes" in output:
                        s_node["planning_notes"] = output["ambiguity_notes"]
                    if "interpretation_confidence" in output:
                         s_node["confidence"] = output["interpretation_confidence"]

            # Capture the Agent's "Thought" process if available (System 2 / React)
            if "status" in node and node["status"] == "completed":
                # Try to find the thought trace in the output
                output = node.get("output", {})
                if isinstance(output, dict):
                    if "thought" in output:
                        s_node["reasoning_thought"] = output["thought"]
                    elif "reasoning" in output:
                        s_node["reasoning_thought"] = output["reasoning"]
                    elif "_reasoning_trace" in output:
                        # Summarize the trace
                        trace = output["_reasoning_trace"]
                        if trace:
                             # Taking the last critique -> refinement interaction as the "thought"
                             last_step = trace[-1]
                             s_node["system2_summary"] = f"Critique: {last_step.get('critique')}\nRefinement: {last_step.get('draft')[:200]}..."
                             s_node["full_reasoning_trace"] = trace 
            
            # 3. Extract Actions (Tools/Calls) without payloads
            actions = []
            if "iterations" in node:
                for iter_data in node["iterations"]:
                    output = iter_data.get("output", {})
                    if not isinstance(output, dict):
                        continue
                    
                    # Capture Tool Calls
                    if output.get("call_tool"):
                        tool_call = output["call_tool"]
                        actions.append({
                            "type": "tool",
                            "name": tool_call.get("name") if isinstance(tool_call, dict) else str(tool_call),
                            # We might strip arguments if they are huge text blocks,
                            # but short args like search queries are valuable.
                            "args": str(tool_call.get("arguments", ""))[:200] if isinstance(tool_call, dict) else ""
                        })

                    # Capture Code Execution
                    if output.get("call_self"):
                        call_self = output.get("call_self", {})
                        actions.append({
                            "type": "code",
                            "lang": "python",
                            # Code is the recipe! Keep it.
                            "snippet": call_self.get("code", "")[:500] if isinstance(call_self, dict) else str(call_self)[:500]
                        })
                        
            s_node["actions"] = actions
            skeleton["nodes"].append(s_node)
            
        return skeleton

class MemoryMiner:
    """
    Extracts analytics and patterns from sessions.
    """
    @staticmethod
    def extract_tool_usage(session_data: Dict) -> List[Dict]:
        """Return list of {tool, success, latency} events"""
        events = []
        # ... logic to mine specific tool successes ...
        return events


def _build_searchable_text(skeleton: Dict) -> str:
    """Build text for embedding: original_query + condensed node descriptions."""
    parts = [str(skeleton.get("original_query", ""))]
    for node in skeleton.get("nodes", []):
        task_goal = node.get("task_goal") or node.get("description")
        if task_goal:
            parts.append(str(task_goal)[:300])
        inst = node.get("instruction")
        if inst:
            parts.append(str(inst)[:300])
    return "\n".join(p for p in parts if p.strip())


class EpisodicMemory:
    def __init__(self):
        self.directory = MEMORY_DIR

    async def save_episode(
        self,
        session_data: Dict,
        space_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """Save episode skeleton. Uses Qdrant when EPISODIC_STORE_PROVIDER=qdrant; local JSON when legacy."""
        try:
            skeleton = MemorySkeletonizer.skeletonize(session_data)
            session_id = skeleton.get("id")
            if not session_id:
                return
            space_id = space_id or SPACE_ID_GLOBAL

            from memory.episodic import get_episodic_store_provider, MEMORY_DIR

            if get_episodic_store_provider() == "legacy":
                path = MEMORY_DIR / f"skeleton_{session_id}.json"
                path.write_text(json.dumps(skeleton, indent=2))
                return

            searchable_text = _build_searchable_text(skeleton)
            if not searchable_text.strip():
                searchable_text = str(skeleton.get("original_query", ""))

            from memory.backends.episodic_qdrant_store import EpisodicQdrantStore
            from remme.utils import get_embedding

            store = EpisodicQdrantStore()
            emb = get_embedding(searchable_text, task_type="search_document")
            store.upsert(
                session_id=str(session_id),
                searchable_text=searchable_text,
                embedding=emb,
                skeleton_json=json.dumps(skeleton),
                original_query=str(skeleton.get("original_query", "")),
                outcome=str(skeleton.get("outcome", "completed")),
                user_id=user_id,
                space_id=space_id,
            )
        except Exception as e:
            log_error(f"Failed to save episodic memory: {e}")

    def search(
        self,
        query: str,
        limit: int = 3,
        user_id: Optional[str] = None,
        space_id: Optional[str] = None,
    ) -> List[Dict]:
        """Find relevant past skeletons. Delegates to memory.episodic.search_episodes."""
        return search_episodes(query, limit=limit, user_id=user_id, space_id=space_id)
