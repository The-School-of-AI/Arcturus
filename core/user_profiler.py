
import asyncio
import time
from typing import List, Dict, Optional
from core.utils import log_step, log_error
from remme.extractor import RemmeExtractor, apply_preferences_to_hubs
from remme.hubs.preferences_hub import get_preferences_hub

class UserProfiler:
    """
    Background worker that extracts user preferences and facts 
    from recent conversations to update the user model.
    """
    def __init__(self):
        self.extractor = RemmeExtractor()
        
    async def profile_session(self, query: str, final_output: str, session_id: str):
        """
        Asynchronously extract and apply preferences from a session.
        """
        log_step(f"👤 Background: Profiling user intent from session {session_id}...", symbol="👤")
        
        # 1. Prepare history for extraction
        history = [{"role": "assistant", "content": final_output}]
        
        try:
            # 2. Extract (using thread to not block)
            commands, preferences = await asyncio.to_thread(
                self.extractor.extract,
                query,
                history
            )
            
            # 3. Apply to hubs
            if preferences:
                changes = await asyncio.to_thread(apply_preferences_to_hubs, preferences)
                if changes:
                    log_step(f"✨ User Model Updated: {len(changes)} preferences refined.", symbol="🧠")
            
            # 4. Save hubs (BaseHub.save updates last_updated timestamp)
            hub = get_preferences_hub()
            hub.save()
            
            return True
        except Exception as e:
            log_error(f"UserProfiler: Background extraction failed - {e}")
            return False

# Singleton instance
_profiler = None

def get_user_profiler() -> UserProfiler:
    global _profiler
    if _profiler is None:
        _profiler = UserProfiler()
    return _profiler
