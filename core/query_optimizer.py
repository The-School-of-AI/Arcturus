import asyncio
from typing import Dict, List, Optional
from core.model_manager import ModelManager
from core.metrics_aggregator import MetricsAggregator
from core.utils import log_step

class QueryOptimizer:
    """
    JitRL (Just-In-Time RL) Optimizer.
    1. Optimizes user queries (Online).
    2. Generates behavioral rules based on past failure patterns (Offline/Background).
    """
    def __init__(self):
        self.model_manager = ModelManager(role="optimizer")
        self.metrics = MetricsAggregator()
        from core.episodic_memory import EpisodicMemory
        self.memory = EpisodicMemory()
        
    async def optimize_query(self, query: str) -> Dict[str, str]:
        """
        Rewrite query to be more precise, decomposed, and agent-friendly.
        Returns: { "original": ..., "optimized": ..., "reasoning": ... }
        """
        # 1. Retrieve Past Successes (JitRL)
        past_skeletons = self.memory.search(query, limit=2)
        past_context = ""
        if past_skeletons:
            past_context = "\n[PAST SUCCESSFUL RECIPES (LEARNINGS)]\n"
            for s in past_skeletons:
                # Format the recipe briefly
                plan = " -> ".join([n.get("agent", "Unknown") for n in s.get("nodes", []) if n.get("agent") != "System"])
                past_context += f"- Task: '{s['original_query']}'\n  Strategy: {plan}\n  Learning: {s.get('nodes', [{}])[1].get('system2_summary', 'N/A')[:100]}...\n"
            past_context += "\nUser Request is similar. ADAPT this successful strategy.\n"

        prompt = f"""
        [TASK]
        You are an Expert Prompt Engineer. Optimize the following user query for an Agentic AI System.
        
        {past_context}

        [USER QUERY]
        {query}
        
        [GOAL]
        1. Clarify ambiguous intents.
        2. Break down complex requests into high-level steps.
        3. Add specific constraints (e.g., "Use Python," "Search for X").
        
        [OUTPUT FORMAT]
        Return ONLY valid JSON:
        {{
            "optimized_query": "The rewritten query...",
            "changes_made": "Explanation of what was improved..."
        }}
        """
        try:
            response = await self.model_manager.generate_text(prompt)
            # Naive parsing (ModelManager usually returns raw text)
            # We trust the model to output JSON or we parse it
            import json
            from core.json_parser import parse_llm_json
            
            data = parse_llm_json(response)
            if isinstance(data, list): data = data[0]
            
            return {
                "original": query,
                "optimized": data.get("optimized_query", query),
                "reasoning": data.get("changes_made", "No changes")
            }
        except Exception as e:
            log_step(f"⚠️ Query optimization failed: {e}")
            return {"original": query, "optimized": query, "reasoning": "Optimization failed"}

    async def get_jit_rules(self) -> str:
        """
        Analyze past session metrics to generate 'Rules of Thumb'.
        Example: If 'BrowserAgent' fails 50% of the time on 'Youtube', 
        generate rule: "Do not use BrowserAgent for Youtube, use YoutubeTool."
        """
        # 1. Get Reliability Matrix
        # In a real system, this would load from disk/DB
        # stats = self.metrics.aggregate_agent_matrix(load_past_sessions())
        
        # Placeholder for now until we connect full session history loading
        rules = []
        
        # Example Logic (Conceptual)
        # if stats['CoderAgent']['error_rate'] > 0.3:
        #     rules.append("CoderAgent: Be extra careful with syntax, verify code before execution.")
            
        return "\n".join(rules)
