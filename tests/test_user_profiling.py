
import asyncio
import unittest
import sys
import os
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from core.user_profiler import get_user_profiler
from remme.hubs.preferences_hub import get_preferences_hub

class TestUserProfiling(unittest.IsolatedAsyncioTestCase):
    async def test_profiling_loop_timestamp_update(self):
        hub = get_preferences_hub()
        
        # 1. Get initial timestamp
        initial_ts = getattr(hub.data.meta, 'last_updated', None)
        print(f"DEBUG: Initial timestamp: {initial_ts}")
        
        # 2. Trigger profiler (mocking extraction for speed)
        profiler = get_user_profiler()
        
        # We'll use a real profile_session call, but we expect it to hit save()
        # which updates the timestamp regardless of whether facts were found.
        # But to be safe, we'll wait a bit.
        
        await profiler.profile_session("What is my name?", "Your name is Rohan.", "test_session_999")
        
        # 3. Get new timestamp
        hub.reload() # Ensure we read from disk if it was saved
        new_ts = getattr(hub.data.meta, 'last_updated', None)
        print(f"DEBUG: New timestamp: {new_ts}")
        
        self.assertIsNotNone(new_ts)
        if initial_ts:
            self.assertGreater(new_ts, initial_ts)
        
        print("✅ User Profiling loop (timestamp update) passed!")

if __name__ == "__main__":
    asyncio.run(unittest.main())
