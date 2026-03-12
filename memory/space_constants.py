"""
P11 Mnemo Phase 3: Spaces / Collections constants.
Phase 4: sync_policy for selective sync.
"""

# Sentinel for global (unscoped) memories/facts. Use in Qdrant payload for filtering.
# In Neo4j: no IN_SPACE relationship = global.
SPACE_ID_GLOBAL = "__global__"

# Sync policy: per-space selective sync (Phase 4); Shared Space step: "shared"
SYNC_POLICY_SYNC = "sync"  # Full sync to cloud/other devices
SYNC_POLICY_LOCAL_ONLY = "local_only"  # Never leave device
SYNC_POLICY_SHARED = "shared"  # Syncs like sync; can be shared with other users
