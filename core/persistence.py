import json
import logging
from pathlib import Path
from typing import Dict, Any

from core.scheduler import scheduler_service
from core.event_bus import event_bus
from shared.state import active_loops

# We need to import AgentLoop4 to re-hydrate, but circular imports might be tricky.
# We'll use lazy imports or assume we just save metadata for now.

logger = logging.getLogger("persistence")
SNAPSHOT_FILE = Path("data/system/snapshot.json")

class PersistenceManager:
    """
    Handles saving and loading the entire system state (OS Snapshot).
    - Active Loops (Agents running)
    - Scheduler Jobs (handled by its own file, but we can verify)
    - Event Bus History (optional)
    """
    
    @staticmethod
    def save_snapshot():
        """Capture current state to disk."""
        try:
            snapshot = {
                "timestamp": None, # Fill in later
                "active_runs": [],
                "event_history_count": len(event_bus._history)
            }
            
            # 1. Capture Active Loops
            # We can't pickle the whole loop (async generators), so we save the 'session_id' and 'query'.
            # On restart, we might need to assume they are "paused" or "failed" or try to resume.
            # For 2026 Vision, we just want to know *what* was running.
            for run_id, loop in active_loops.items():
                # Extract graph status if possible
                status = "unknown"
                query = "unknown"
                if loop.context and loop.context.plan_graph:
                    status = loop.context.plan_graph.graph.get("status", "running")
                    query = loop.context.plan_graph.graph.get("original_query", "")
                    
                snapshot["active_runs"].append({
                    "run_id": run_id,
                    "status": status,
                    "query": query
                })
            
            # Ensure directory
            if not SNAPSHOT_FILE.parent.exists():
                SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
                
            SNAPSHOT_FILE.write_text(json.dumps(snapshot, indent=2))
            logger.info(f"✅ System Snapshot saved ({len(snapshot['active_runs'])} runs)")
            
        except Exception as e:
            logger.error(f"❌ Failed to save snapshot: {e}")

    @staticmethod
    def load_snapshot():
        """Restore state on startup."""
        if not SNAPSHOT_FILE.exists():
            return
            
        try:
            data = json.loads(SNAPSHOT_FILE.read_text())
            runs = data.get("active_runs", [])
            
            # For now, just log what we found. Re-hydration logic (re-starting loops) 
            # is complex and depends on how "pausable" the agents are.
            # We will emit an event so the UI knows.
            
            logger.info(f"♻️ Restoring Snapshot: {len(runs)} previous runs found.")
            
            for run in runs:
                # In a real OS, we would restart them. 
                # For now, we just notify the admin console.
                if run["status"] == "running":
                    logger.warning(f"⚠️ Run {run['run_id']} was interrupted. Query: {run['query']}")
                    
            # TODO: Auto-resume logic
            
        except Exception as e:
            logger.error(f"❌ Failed to load snapshot: {e}")

persistence_manager = PersistenceManager()
