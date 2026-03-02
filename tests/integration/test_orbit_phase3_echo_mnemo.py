import pytest
import asyncio
import time
from nodes.sync import EchoMnemoSyncManager, exponential_backoff_retry
from nodes.protocol import Capability, DeviceNode, NodeInvocation
from channels.mobile import MobileAdapter

@pytest.mark.asyncio
async def test_exponential_backoff_success() -> None:
    """Test that exponential backoff succeeds eventually."""
    attempts = 0
    
    async def mock_func():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("Transient failure")
        return "success"
    
    result = await exponential_backoff_retry(mock_func, max_retries=5, base_delay=0.1)
    assert result == "success"
    assert attempts == 3

@pytest.mark.asyncio
async def test_exponential_backoff_failure() -> None:
    """Test that exponential backoff fails after max retries."""
    async def mock_func():
        raise ConnectionError("Persistent failure")
    
    with pytest.raises(ConnectionError):
        await exponential_backoff_retry(mock_func, max_retries=3, base_delay=0.1)

def test_conflict_resolution_lww() -> None:
    """Test Last-Write-Wins conflict resolution."""
    manager = EchoMnemoSyncManager()
    
    local_item = {
        "id": "mem_1",
        "value": "updated_local",
        "local_timestamp": 200.0
    }
    remote_item = {
        "id": "mem_1",
        "value": "updated_remote",
        "local_timestamp": 100.0
    }
    
    winner = manager.resolve_conflict_lww(local_item, remote_item)
    assert winner["value"] == "updated_local"
    
    # Remote wins
    remote_item["local_timestamp"] = 300.0
    winner2 = manager.resolve_conflict_lww(local_item, remote_item)
    assert winner2["value"] == "updated_remote"

@pytest.mark.asyncio
async def test_sync_manager_queue_processing() -> None:
    """Test that the sync manager processes its queue correctly."""
    manager = EchoMnemoSyncManager()
    synced_items = []
    
    async def mock_sync(node_id, payload):
        synced_items.append(payload)
        return {"status": "ok"}
    
    manager.queue_intent({"id": 1, "local_timestamp": 10.0})
    manager.queue_intent({"id": 2, "local_timestamp": 20.0})
    
    assert len(manager.offline_queue) == 2
    
    await manager.process_sync_queue("test-node", mock_sync)
    
    assert len(synced_items) == 2
    assert len(manager.offline_queue) == 0

@pytest.mark.asyncio
async def test_mobile_adapter_nack_requeuing() -> None:
    """Test that NACKing messages in MobileAdapter re-enqueues them at the front."""
    adapter = MobileAdapter()
    session_id = "session-p3"
    
    # Clear outbox just in case
    adapter.drain_outbox(session_id)
    
    # 1. Send some messages
    await adapter.send_message(session_id, "Message 1")
    await adapter.send_message(session_id, "Message 2")
    
    # 2. Drain them
    messages = adapter.drain_outbox(session_id)
    assert len(messages) == 2
    
    # 3. Simulate NACK for Message 1
    # Note: messages[0] is "Message 1"
    adapter.nack_messages(session_id, [messages[0]])
    
    # 4. Drain again - should have Message 1
    remains = adapter.drain_outbox(session_id)
    assert len(remains) == 1
    assert remains[0]["content"] == "Message 1"

def test_protocol_new_capabilities_and_metadata() -> None:
    """Verify Phase 3 protocol fields exist and serialize correctly."""
    node = DeviceNode(
        node_id="p3-phone",
        name="Phase 3 Phone",
        device_type="mobile",
        capabilities=[Capability.OFFLINE_SYNC, Capability.CONFLICT_RESOLUTION],
        vector_clock={"node-a": 5}
    )
    
    data = node.to_dict()
    assert "offline_sync" in data["capabilities"]
    assert data["vector_clock"]["node-a"] == 5
    
    inv = NodeInvocation(
        target_node_id="p3-phone",
        capability=Capability.OFFLINE_SYNC,
        action="sync_memory",
        idempotency_key="key-123",
        local_timestamp=123456.789
    )
    
    inv_data = inv.to_dict()
    assert inv_data["idempotency_key"] == "key-123"
    assert inv_data["local_timestamp"] == 123456.789
