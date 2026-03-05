"""Sync and Conflict Resolution logic for Project 13: Orbit.

This module provides utilities for handling synchronization between Echo voice 
intents and Mnemo memory updates, specifically addressing offline-to-online 
transitions and concurrent modification conflicts.
"""

import asyncio
import time
from typing import Any, Dict, List, Optional, Callable
from core.utils import log_step, log_error

async def exponential_backoff_retry(
    async_func: Callable,
    max_retries: int = 5,
    base_delay: float = 1.0,
    retryable_errors: tuple = (asyncio.TimeoutError, ConnectionError, TimeoutError),
    on_retry: Optional[Callable[[int, float], None]] = None,
):
    """
    Retry an async function with exponential backoff.
    
    Args:
        async_func: Async callable to execute.
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds.
        retryable_errors: Tuple of exceptions that trigger a retry.
        on_retry: Optional callback receiving (attempt_number, current_delay).
    """
    last_exception = None
    for attempt in range(max_retries):
        try:
            return await async_func()
        except retryable_errors as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                if on_retry:
                    on_retry(attempt + 1, delay)
                log_step(
                    f"Sync retry: {type(e).__name__} (attempt {attempt + 1}/{max_retries}) - waiting {delay}s",
                    symbol="REFRESH"
                )
                await asyncio.sleep(delay)
            else:
                log_error(f"Sync failed after {max_retries} retries: {e}")
        except Exception:
            # Raise non-retryable exceptions immediately
            raise

    if last_exception:
        raise last_exception


class EchoMnemoSyncManager:
    """Manages synchronization between Echo (voice intents) and Mnemo (memory updates)."""

    def __init__(self):
        self.offline_queue: List[Dict[str, Any]] = []

    def resolve_conflict_lww(self, local_item: Dict[str, Any], remote_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Conflict resolution using Last-Write-Wins (LWW) logic based on local_timestamp.
        
        Args:
            local_item: The data from the local device node.
            remote_item: The data currently stored in the remote memory (Mnemo).
            
        Returns:
            The winning dictionary of data.
        """
        local_ts = local_item.get("local_timestamp", 0)
        remote_ts = remote_item.get("local_timestamp", 0)

        # In case of tie, local wins (consistent with mobile-first strategy)
        if local_ts >= remote_ts:
            log_step("Conflict resolution: LWW strategy applied (Local wins)", symbol="SYNC")
            return local_item
        else:
            log_step("Conflict resolution: LWW strategy applied (Remote wins)", symbol="SYNC")
            return remote_item

    async def process_sync_queue(self, node_id: str, sync_func: Callable):
        """
        Drains the offline queue and attempts to sync items to Mnemo using backoff.
        
        Args:
            node_id: ID of the node being synchronized.
            sync_func: Async function(node_id, payload) that performs the remote update.
        """
        if not self.offline_queue:
            return

        log_step(f"Processing {len(self.offline_queue)} queued sync items for node {node_id}")
        
        indices_to_remove = []
        for i, payload in enumerate(self.offline_queue):
            try:
                # Use lambda to pass arguments to the async sync function
                await exponential_backoff_retry(lambda: sync_func(node_id, payload))
                indices_to_remove.append(i)
                log_step(f"Successfully synced item {payload.get('idempotency_key', i)}")
            except Exception as e:
                log_error(f"Failed to sync item {payload.get('idempotency_key', i)}: {e}")
                # Stop processing if a fatal error occurs or retries are exhausted
                break

        # Remove successfully synced items (reverse order to maintain indices)
        for i in sorted(indices_to_remove, reverse=True):
            self.offline_queue.pop(i)

    def queue_intent(self, payload: Dict[str, Any]):
        """Adds a voice intent or memory update to the offline queue."""
        self.offline_queue.append(payload)
        log_step(f"Item queued for sync: {payload.get('idempotency_key', 'unnamed')}", symbol="MEM")
