import asyncio
import os
import sys

# Add root to path
sys.path.append(os.getcwd())

from core.reasoning import Verifier

async def test():
    print("--- Verifying Emergency Fix ---")
    print("Attempting to initialize Verifier (which is configured to use strict local model 'phi4')...")
    
    try:
        v = Verifier()
        print("✅ Verifier initialized successfully (No crash).")
        
        if v.model_manager is None:
             print("ℹ️ State: ModelManager is None. Verification will be SKIPPED (Safe Fallback).")
        else:
             print(f"ℹ️ State: Verifier using provider '{v.model_manager.model_type}' model '{v.model_manager.text_model_key}'.")
             
        # Test verify
        print("Testing verify() method...")
        score, critique = await v.verify("test query", "test draft")
        print(f"✅ verify() returned: Score={score}, Critique='{critique}'")
        
    except Exception as e:
        print(f"❌ CRITICAL FAILURE: Verifier crashed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test())
