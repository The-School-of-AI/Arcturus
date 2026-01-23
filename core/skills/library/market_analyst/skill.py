from typing import List, Any, Dict
from core.skills.base import BaseSkill, SkillMetadata
from pathlib import Path
import json

class MarketAnalystSkill(BaseSkill):
    def get_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="market_analyst",
            version="1.0.0",
            description="Analyzes stock markets and news using Yahoo Finance and Web Search",
            author="Arcturus System",
            intent_triggers=["stock price", "market analysis", "news briefing", "finance update", "price", "news", "value", "funding", "market"]
        )

    def get_tools(self) -> List[Any]:
        # Ideally, we return specific tool definitions here.
        # For now, we rely on the generic agent having access to global MCP servers.
        # In v2, we would return specific function pointers.
        return [] 

    async def on_run_start(self, initial_prompt: str) -> str:
        """Inject specific guidance for market analysis"""
        return f"""
        You are the Market Analyst Mode.
        Task: {initial_prompt}
        
        Instructions:
        1. Use 'yahoo_finance' tools (get_stock_price, get_company_news) heavily.
        2. Cross-reference with Web Search if needed.
        3. Be concise and data-driven.
        4. Always include a final 'FormatterAgent' step to produce a cohesive Markdown report.
        """.strip()

    async def on_run_success(self, artifact: Dict[str, Any]):
        """
        Save the output to a structured Briefing note or user-specified path.
        """
        import re
        content = artifact.get("summary") or artifact.get("output")
        
        # Robust logic: if summary is just "Completed." but we have structured output,
        # don't overwrite the work done by the agent (which might have already saved the file).
        if content == "Completed." or not content:
             # Look for other keys in artifact
             for k, v in artifact.items():
                 if isinstance(v, str) and len(v) > 100:
                     content = v
                     break
        
        if not content or content == "Completed.":
             # Special case: if it was a success but we only have "Completed.", 
             # and the target file already exists, maybe the agent saved it.
             # We should avoid overwriting it with a generic message.
             content = "Completed."
        
        # Check for failure
        if artifact.get("status") == "failed":
            content = f"❌ Analysis Failed: {artifact.get('error', 'Unknown error')}"

        # ... rest of the method logic for path determination ...
        
        user_path = None
        if self.context.config and "query" in self.context.config:
            q = self.context.config["query"]
            match = re.search(r"(?:store|save|write).+?(?:in|to)\s+([a-zA-Z0-9_/.]+\.md)", q, re.IGNORECASE)
            if match:
                user_path = match.group(1).strip()
        
        if user_path:
            clean_path = user_path.lstrip("/")
            if clean_path.startswith("data/"):
                clean_path = clean_path[5:]
            target = Path(f"data/{clean_path}")
        else:
            notes_dir = Path("data/Notes/Briefing")
            notes_dir.mkdir(parents=True, exist_ok=True)
            target = notes_dir / f"Market_Briefing_{self.context.run_id}.md"

        # IMPORTANT: If the file already exists and is large, and our new content is "Completed.",
        # do NOT overwrite it!
        if target.exists() and content == "Completed." and target.stat().st_size > 100:
            print(f"ℹ️ Skipping overwrite of {target} with placeholder info.")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"# 📈 Market Briefing\n\n{content}")
            print(f"✅ Market Analyst saved briefing to {target}")
        
        return {
            "file_path": str(target),
            "type": "briefing",
            "summary": content[:200] + ("..." if len(content) > 200 else "")
        }

