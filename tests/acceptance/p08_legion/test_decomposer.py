
import pytest
import ray
import asyncio
from agents.manager import ManagerAgent
from agents.swarm_runner import SwarmRunner
from agents.protocol import Task

# Mark as async test
@pytest.mark.asyncio
async def test_manager_decomposition():
    """
    Test that the ManagerAgent can decompose a request into a valid list of tasks.
    """
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True)
        
    manager = ManagerAgent.remote()
    request = "Research quantum computing and write a summary."
    
    # Execute decomposition
    tasks_data = await manager.decompose_task.remote(request)
    
    assert isinstance(tasks_data, list)
    assert len(tasks_data) > 0
    
    # Verify task structure
    for t_data in tasks_data:
        task = Task(**t_data)
        assert task.title is not None
        assert task.status == "pending"
        
    ray.shutdown()

@pytest.mark.asyncio
async def test_swarm_execution_flow():
    """
    Test the full execution flow via SwarmRunner.
    """
    runner = SwarmRunner()
    await runner.initialize()
    
    results = await runner.run_request("Research quantum computing and write a summary.")
    
    assert len(results) == 2 # Based on our mock logic (Research + Write)
    
    # Verify states
    for res in results:
        task = Task(**res)
        assert task.status == "completed"
        assert task.result is not None
        
    await runner.shutdown()
