
import sys
import os
sys.path.append(os.getcwd())
import asyncio
import unittest
import shutil
from pathlib import Path
from core.loop import AgentLoop4
from memory.context import ExecutionContextManager
from unittest.mock import MagicMock, AsyncMock

class TestLoopResume(unittest.TestCase):
    def setUp(self):
        # Setup temp directory for sessions
        self.test_dir = Path("memory/session_summaries_index/2026/02/16")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = "test_resume_session"
        self.session_file = self.test_dir / f"session_{self.session_id}.json"

    def tearDown(self):
        # Clean up
        if self.session_file.exists():
            self.session_file.unlink()

    def test_resume_logic(self):
        # 1. Create a "stopped" session file
        graph_data = {
            "nodes": [
                {"id": "ROOT", "status": "completed", "agent": "System"},
                {"id": "Step1", "status": "completed", "agent": "AgentA", "output": {"result": "done"}},
                {"id": "Step2", "status": "stopped", "agent": "AgentB"}, # Interrupted step
                {"id": "Step3", "status": "pending", "agent": "AgentC"}
            ],
            "edges": [
                {"source": "ROOT", "target": "Step1"},
                {"source": "Step1", "target": "Step2"},
                {"source": "Step2", "target": "Step3"}
            ],
            "globals_schema": {"var1": "value1"},
            "session_id": self.session_id,
            "original_query": "Test Query"
        }
        
        # Save it manually using Context (to reuse its saving logic)
        context = ExecutionContextManager(graph_data, session_id=self.session_id)
        context.plan_graph.nodes["Step2"]["status"] = "stopped" # Force stopped status
        context._save_session()
        
        # DEBUG: Read file and check keys
        import json
        with open(self.session_file, 'r') as f:
            saved_data = json.load(f)
            print(f"DEBUG: Saved JSON keys: {list(saved_data.keys())}")
            if "links" in saved_data:
                print(f"DEBUG: links count: {len(saved_data['links'])}")
            if "edges" in saved_data:
                print(f"DEBUG: edges count: {len(saved_data['edges'])}")
        
        # 2. Mock AgentLoop dependencies
        mock_mcp = MagicMock()
        loop = AgentLoop4(mock_mcp)
        loop.agent_runner = MagicMock()
        loop.agent_runner.run_agent = AsyncMock(return_value={"success": True, "output": {"result": "resumed"}})
        
        # 3. Call Resume (We expect this method to exist/work)
        # We need to implement loop.resume(session_file)
        # For this test, we assume we will implement it.
        
        # Mock _execute_dag to avoid infinite loops or actual execution, 
        # but we want to verify it was called with corrected context.
        loop._execute_dag = AsyncMock(return_value=None)
        
        asyncio.run(loop.resume(self.session_file))
        
        # 4. Verify "stopped" node was reset to "pending"
        # We need to inspect the context passed to _execute_dag
        call_args = loop._execute_dag.call_args
        self.assertIsNotNone(call_args, "execute_dag was not called")
        
        resumed_context = call_args[0][0]
        step2_status = resumed_context.plan_graph.nodes["Step2"]["status"]
        self.assertEqual(step2_status, "pending", "Stopped node should be reset to pending")
        
        step3_status = resumed_context.plan_graph.nodes["Step3"]["status"]
        self.assertEqual(step3_status, "pending", "Pending node should remain pending")

if __name__ == "__main__":
    unittest.main()
