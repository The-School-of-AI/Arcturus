import json
import asyncio
from pathlib import Path
from typing import Dict, List, Any
from core.utils import log_step, log_error

MEMORY_DIR = Path(__file__).parent.parent / "memory" / "episodes"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

class MemorySkeletonizer:
    """
    Compresses full execution graphs into lightweight 'Skeletons' (Recipes).
    Removes heavy payloads (HTML, huge text) but preserves Logic (Prompts, Tool Calls).
    """
    @staticmethod
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
                    
                    # Capture Tool Calls
                    if output.get("call_tool"):
                        tool_call = output["call_tool"]
                        actions.append({
                            "type": "tool",
                            "name": tool_call.get("name"),
                            # We might strip arguments if they are huge text blocks, 
                            # but short args like search queries are valuable.
                            "args": str(tool_call.get("arguments", ""))[:200] 
                        })
                    
                    # Capture Code Execution
                    if output.get("call_self"):
                        actions.append({
                            "type": "code",
                            "lang": "python",
                            # Code is the recipe! Keep it.
                            "snippet": output.get("call_self", {}).get("code", "")[:500] 
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

class EpisodicMemory:
    def __init__(self):
        self.directory = MEMORY_DIR
        
    async def save_episode(self, session_data: Dict):
        """Save a skeletonized version of the episode"""
        try:
            skeleton = MemorySkeletonizer.skeletonize(session_data)
            
            # Save as JSON
            session_id = skeleton["id"]
            if not session_id:
                return
                
            file_path = self.directory / f"skeleton_{session_id}.json"
            file_path.write_text(json.dumps(skeleton, indent=2))
            
            log_step(f"🧠 Saved Episode Skeleton: {file_path.name} ({len(json.dumps(skeleton))} bytes)", symbol="💾")
            
        except Exception as e:
            log_error(f"Failed to save episodic memory: {e}")
            
    def search(self, query: str, limit=3) -> List[Dict]:
        """
        Find relevant past skeletons based on query similarity.
        Uses simple Jaccard similarity on tokens.
        """
        if not self.directory.exists():
            return []
            
        query_tokens = set(query.lower().split())
        candidates = []
        
        for f in self.directory.glob("skeleton_*.json"):
            try:
                data = json.loads(f.read_text())
                original_q = data.get("original_query", "")
                if not original_q:
                    continue
                    
                target_tokens = set(original_q.lower().split())
                
                # Jaccard Similarity: Intersection / Union
                intersection = query_tokens.intersection(target_tokens)
                union = query_tokens.union(target_tokens)
                
                if not union:
                    score = 0
                else:
                    score = len(intersection) / len(union)
                
                if score > 0.1: # Threshold to avoid noise
                    candidates.append((score, data))
            except Exception:
                continue
                
        # Sort by score desc
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        return [c[1] for c in candidates[:limit]]
