from typing import List, Any, Dict
from core.skills.base import BaseSkill, SkillMetadata
from pathlib import Path
import re
import aiohttp

class WebClipperSkill(BaseSkill):
    def get_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="web_clipper",
            version="1.0.0",
            description="Downloads and archives web pages to Notes",
            author="Arcturus",
            intent_triggers=["clip url", "archive page", "save website", "download html"]
        )

    def get_tools(self) -> List[Any]:
        return []

    async def on_run_start(self, initial_prompt: str) -> str:
        return initial_prompt

    async def on_run_success(self, artifact: Dict[str, Any]):
        # Extract URL from context.config['query']
        query = self.context.config.get("query", "")
        url_match = re.search(r"https?://[^\s]+", query)
        
        if not url_match:
            print("❌ Web Clipper: No URL found in query")
            return

        url = url_match.group(0)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    text = await resp.text()
                    
            # Basic HTML cleanup (placehoder for real parsing)
            # In real world, use readability or similar.
            clean_text = text[:5000] # Truncate for safety
            
            report = f"# 📎 Web Clip: {url}\n\n```html\n{clean_text}\n```"
            
            # Save
            safe_name = re.sub(r"[^a-zA-Z0-9]", "_", url)[:50]
            target = Path(f"data/Notes/Clips/{safe_name}_{self.context.run_id}.md")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(report)
            print(f"✅ Web Clipper saved clone to {target}")
            
            return {
                "file_path": str(target),
                "type": "web_clip",
                "url": url,
                "summary": f"Clipped {url}"
            }
            
        except Exception as e:
            print(f"❌ Web Clipper failed: {e}")
            return {"error": str(e)}
