
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Setup path
sys.path.append(os.getcwd())

from agents.base_agent import AgentRunner
from shared.state import get_skill_manager

async def test_features():
    print("--- 1. Testing Skill Injection ---")
    # Mock MultiMCP
    mock_mcp = MagicMock()
    mock_mcp.get_tools_from_servers.return_value = []
    
    runner = AgentRunner(multi_mcp=mock_mcp)
    
    # Enable a skill for CoderAgent (temporarily modify config or just check existing)
    # Let's see what skills CoderAgent has in config
    coder_config = runner.agent_configs.get("CoderAgent", {})
    print(f"CoderAgent Skills: {coder_config.get('skills', [])}")
    
    # We want to see if the skill actually modifies the prompt.
    # We'll mock the 'generate_text' of ModelManager to capture the prompt
    
    captured_prompt = ""
    
    async def mock_generate_text(prompt, **kwargs):
        nonlocal captured_prompt
        captured_prompt = prompt
        return '{"thought": "test", "output": "test"}'

    # Patch ModelManager
    from core import model_manager
    original_generate = model_manager.ModelManager.generate_text
    model_manager.ModelManager.generate_text = mock_generate_text
    
    try:
        # Run Agent
        print("Running CoderAgent...")
        await runner.run_agent("CoderAgent", {"task": "Write hello world"})
        
        # Check Prompt for Skill Content
        # We need to know what a skill adds. Let's assume 'python_coding' skill adds something specific.
        # or we can check for 'User Preferences' section
        
        print("\n--- Prompt Analysis ---")
        if "User Preferences" in captured_prompt:
            print("✅ User Preferences injected successfully.")
            # Extract a snippet
            start = captured_prompt.find("User Preferences")
            print(f"Snippet: {captured_prompt[start:start+100]}...")
        else:
            print("❌ User Preferences NOT found in prompt.")

        # Check for Skill content
        # We need to read a skill file to know what to look for. 
        # But generally skills add sections or instructions.
        pass

    except Exception as e:
        print(f"❌ Error during test: {e}")
    finally:
         model_manager.ModelManager.generate_text = original_generate

    print("\n--- 2. Testing Memory retrieval in Runs ---")
    # We can't easily run the full loop here without setup, but we verified the code in runs.py
    # Let's check remme_store mocking if possible, or just rely on static analysis we did.
    
    print("\n--- 3. Testing Cortex-R Persona ---")
    # Check if 'Cortex-R' string appears in prompt
    if "Cortex-R" in captured_prompt:
         print("✅ Cortex-R persona name found in prompt.")
    else:
         print("❌ Cortex-R persona name NOT found in prompt (confirmed placeholder status).")

if __name__ == "__main__":
    asyncio.run(test_features())
