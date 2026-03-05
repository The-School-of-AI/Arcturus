"""Device Node Protocol for Project 13: Orbit.

This module defines how devices (mobile, desktop companions) advertise 
capabilities and receive remote invocations via the Arcturus gateway.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
import time


class NodeStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    ERROR = "error"


class Capability(str, Enum):
    CHAT = "chat"
    VOICE = "voice"
    CAMERA = "camera"
    SCREEN_CAPTURE = "screen_capture"
    NOTIFICATIONS = "notifications"
    FILES = "files"
    GPS = "gps"
    DOCUMENT_SCAN = "document_scan"
    OFFLINE_SYNC = "offline_sync"
    CONFLICT_RESOLUTION = "conflict_resolution"


@dataclass
class DeviceNode:
    """Represents a remote device connected to the Arcturus network."""

    node_id: str
    name: str
    device_type: str  # "mobile_ios", "mobile_android", "desktop_macos", etc.
    status: NodeStatus = NodeStatus.ONLINE
    capabilities: List[Capability] = field(default_factory=list)
    last_seen: float = field(default_factory=time.time)
    vector_clock: Dict[str, int] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize node for transmission."""
        return {
            "node_id": self.node_id,
            "name": self.name,
            "device_type": self.device_type,
            "status": self.status.value,
            "capabilities": [c.value for c in self.capabilities],
            "last_seen": self.last_seen,
            "vector_clock": self.vector_clock,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeviceNode":
        """Deserialize node from dictionary."""
        return cls(
            node_id=data["node_id"],
            name=data["name"],
            device_type=data["device_type"],
            status=NodeStatus(data.get("status", "online")),
            capabilities=[Capability(c) for c in data.get("capabilities", [])],
            last_seen=data.get("last_seen", time.time()),
            vector_clock=data.get("vector_clock", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass
class NodeInvocation:
    """Represents a request to invoke a capability on a specific node."""

    invocation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    target_node_id: str = ""
    capability: Capability = Capability.CHAT
    action: str = ""  # e.g., "take_photo", "start_recording"
    params: Dict[str, Any] = field(default_factory=dict)
    attachment_id: Optional[str] = None  # Reference to binary data in vault/storage
    timestamp: float = field(default_factory=time.time)
    idempotency_key: Optional[str] = None
    local_timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "invocation_id": self.invocation_id,
            "target_node_id": self.target_node_id,
            "capability": self.capability.value,
            "action": self.action,
            "params": self.params,
            "attachment_id": self.attachment_id,
            "timestamp": self.timestamp,
            "idempotency_key": self.idempotency_key,
            "local_timestamp": self.local_timestamp,
        }
