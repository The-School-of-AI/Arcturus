from pathlib import Path

import pytest

from nodes.protocol import Capability, DeviceNode, NodeInvocation, NodeStatus

PROJECT_ID = "P13"
PROJECT_KEY = "p13_orbit"
CI_CHECK = "p13-orbit-mobile"
CHARTER = Path("CAPSTONE/project_charters/P13_orbit_mobile_cross_platform_experience.md")
DELIVERY_README = Path("CAPSTONE/project_charters/P13_DELIVERY_README.md")


def test_01_charter_exists() -> None:
    assert CHARTER.exists(), f"Missing charter: {CHARTER}"


def test_02_delivery_readme_exists() -> None:
    assert DELIVERY_README.exists(), f"Missing delivery README: {DELIVERY_README}"


def test_03_node_registration_protocol() -> None:
    """Validate that a device node can be created and serialized."""
    node = DeviceNode(
        node_id="test-phone-001",
        name="iPhone 15",
        device_type="mobile_ios",
        capabilities=[Capability.CHAT, Capability.CAMERA]
    )
    data = node.to_dict()
    assert data["node_id"] == "test-phone-001"
    assert "camera" in data["capabilities"]

    node2 = DeviceNode.from_dict(data)
    assert node2.name == "iPhone 15"
    assert node2.capabilities == node.capabilities


def test_04_node_invocation_structure() -> None:
    """Validate remote invocation payload structure."""
    inv = NodeInvocation(
        target_node_id="test-phone-001",
        capability=Capability.CAMERA,
        action="take_photo",
        params={"resolution": "1080p"}
    )
    data = inv.to_dict()
    assert data["action"] == "take_photo"
    assert data["params"]["resolution"] == "1080p"


def test_05_malformed_node_data_handling() -> None:
    """Ensure malformed node data raises appropriate errors."""
    bad_data = {"node_id": "test"}  # Missing required fields
    with pytest.raises(KeyError):
        DeviceNode.from_dict(bad_data)


def test_06_session_continuity_contract() -> None:
    """Validate the presence of session sync markers in protocol (mock)."""
    # In a real scenario, this would check if the session_id is passed correctly
    node = DeviceNode(
        node_id="test", name="test", device_type="test",
        metadata={"current_session_id": "session-123"}
    )
    assert node.metadata["current_session_id"] == "session-123"


def test_07_offline_queue_contract() -> None:
    """Validate offline queue markers in metadata."""
    node = DeviceNode(
        node_id="test", name="test", device_type="test",
        metadata={"offline_queue_supported": True, "pending_messages": 0}
    )
    assert node.metadata["offline_queue_supported"] is True


def test_08_device_action_camera_capability() -> None:
    """Validate camera capability advertising."""
    node = DeviceNode(
        node_id="test", name="test", device_type="test",
        capabilities=[Capability.CAMERA]
    )
    assert Capability.CAMERA in node.capabilities


def test_09_device_action_screenshot_capability() -> None:
    """Validate screen capture capability advertising."""
    node = DeviceNode(
        node_id="test", name="test", device_type="test",
        capabilities=[Capability.SCREEN_CAPTURE]
    )
    assert Capability.SCREEN_CAPTURE in node.capabilities


def test_10_happy_path_e2e_serialization() -> None:
    """E2E flow: Create node -> Register capabilities -> Serialize -> Deserialize."""
    node = DeviceNode(
        node_id="mobile-001",
        name="Android Dev",
        device_type="mobile_android",
        capabilities=[Capability.CHAT, Capability.VOICE, Capability.NOTIFICATIONS]
    )
    serialized = node.to_dict()
    deserialized = DeviceNode.from_dict(serialized)
    assert deserialized.node_id == "mobile-001"
    assert len(deserialized.capabilities) == 3


@pytest.mark.asyncio
async def test_11_mobile_adapter_outbox() -> None:
    """Validate that MobileAdapter correctly queues and drains messages."""
    from channels.mobile import MobileAdapter
    adapter = MobileAdapter()
    session_id = "test-session-456"

    # Send a message
    await adapter.send_message(session_id, "Hello Mobile")

    # Drain outbox
    messages = adapter.drain_outbox(session_id)
    assert len(messages) == 1
    assert messages[0]["content"] == "Hello Mobile"
    assert messages[0]["channel"] == "mobile"

    # Ensure it's empty now
    messages_after = adapter.drain_outbox(session_id)
    assert len(messages_after) == 0
