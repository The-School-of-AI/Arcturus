
import asyncio
import os
import sys
from unittest.mock import MagicMock

# Setup path
sys.path.append(os.getcwd())

from agents.base_agent import AgentRunner

async def test_features():
    print("--- 1. Testing Skill Injection ---")
    mock_mcp = MagicMock()
    mock_mcp.get_tools_from_servers.return_value = []
    
    runner = AgentRunner(multi_mcp=mock_mcp)
    
    captured_prompt = ""
    
    # Fix the mock signature to accept 'self'
    async def mock_generate_text(self, prompt, **kwargs):
        nonlocal captured_prompt
        captured_prompt = prompt
        return '{"thought": "test", "output": "test"}'

    # Patch ModelManager
    from core import model_manager
    original_generate = model_manager.ModelManager.generate_text
    model_manager.ModelManager.generate_text = mock_generate_text
    
    try:
        print("Running CoderAgent...")
        await runner.run_agent("CoderAgent", {"task": "Write hello world"})
        
        print("\n--- Prompt Analysis ---")
        if "User Preferences" in captured_prompt:
            print("✅ User Preferences injected successfully.")
            start = captured_prompt.find("User Preferences")
            print(f"Snippet: {captured_prompt[start:start+200]}...")
        else:
            print("❌ User Preferences NOT found in prompt.")

        # Check for Firecrawl Skill content
        # I happen to know firecrawl skill might add "Firecrawl" or specific instructions.
        if "firecrawl" in captured_prompt.lower():
             print("✅ Firecrawl Skill content found in prompt.")
        else:
             print("❌ Firecrawl Skill content NOT found in prompt.")
             
        # Check for Cortex-R
        if "Cortex-R" in captured_prompt:
             print("✅ Cortex-R persona name found.")
        else:
             print("❌ Cortex-R persona name NOT found.")

    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
         model_manager.ModelManager.generate_text = original_generate

if __name__ == "__main__":
    asyncio.run(test_features())
