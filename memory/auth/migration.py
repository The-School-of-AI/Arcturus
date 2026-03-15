"""
Guest → Registered user migration.

This module is the single entry point for migrating a guest user's data to a
registered account. All flows that reassign ownership (e.g. after registration)
should call migrate_guest_to_registered() only; do not perform ad-hoc Qdrant
payload updates or Neo4j rewiring elsewhere.
"""
import uuid
import logging
from typing import Optional

from shared.state import get_remme_store
from memory.knowledge_graph import KnowledgeGraph, get_knowledge_graph
from memory.mnemo_config import is_mnemo_enabled
from qdrant_client.http.models import UpdateResult, UpdateStatus

logger = logging.getLogger(__name__)


async def migrate_guest_to_registered(guest_id: uuid.UUID, registered_id: uuid.UUID) -> bool:
    """
    Migrates all data owned by a guest user to a registered user account.
    Single entry point for guest→registered migration; use this instead of
    ad-hoc Qdrant/Neo4j updates.

    This includes:
    1. Qdrant vector payloads (memories)
    2. Neo4j Knowledge Graph nodes (User relationships, Session ownership, Space ownership, Facts)

    Returns True if migration succeeded.
    """
    guest_id_str = str(guest_id)
    reg_id_str = str(registered_id)
    
    logger.info(f"Starting data migration from guest {guest_id_str} to registered user {reg_id_str}")
    
    try:
        # --- 1. Migrate Qdrant Vector Payloads ---
        # Get the Qdrant store via shared state abstract factory
        vector_store = get_remme_store()
        
        # We need to access the underlying Qdrant client directly to perform an update-by-filter
        if hasattr(vector_store, 'client') and hasattr(vector_store, 'collection_name'):
            client = vector_store.client
            collection_name = vector_store.collection_name
            
            # Use Qdrant's Scroll API to find all points belonging to the guest
            from qdrant_client.http.models import Filter, FieldCondition, MatchValue
            
            guest_filter = Filter(
                must=[
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(value=guest_id_str)
                    )
                ]
            )
            
            # Fetch all points (assuming < 10,000 for a guest, otherwise we'd need true pagination)
            records, _ = client.scroll(
                collection_name=collection_name,
                scroll_filter=guest_filter,
                limit=10000,
                with_payload=True,
                with_vectors=False
            )
            
            if records:
                point_ids = [record.id for record in records]
                logger.info(f"Found {len(point_ids)} Qdrant points to migrate.")
                
                # Update payload using set_payload
                client.set_payload(
                    collection_name=collection_name,
                    payload={"user_id": reg_id_str},
                    points=point_ids
                )
                logger.info("Qdrant migration complete.")
            else:
                logger.info("No Qdrant points found for guest; skipping.")

        
        # --- 2. Migrate Neo4j Knowledge Graph ---
        if is_mnemo_enabled():
            kg = get_knowledge_graph()
            if kg and kg._driver:
                logger.info("Migrating Neo4j graph data...")
                
                # We do this in a single explicit transaction to ensure atomicity
                with kg._driver.session() as session:
                    session.execute_write(_neo4j_migration_tx, guest_id_str, reg_id_str)
                    
                logger.info("Neo4j migration complete.")
                
        return True
        
    except Exception as e:
        logger.error(f"Migration failed from {guest_id_str} to {reg_id_str}: {e}", exc_info=True)
        return False


def _neo4j_migration_tx(tx, guest_id: str, reg_id: str):
    """
    Neo4j transaction function to merge a guest user node into a real user node,
    and update all `user_id` properties on Fact nodes.
    """
    
    # Ensure the target registered User node exists
    tx.run(
        "MERGE (u:User {id: $reg_id}) SET u.user_id = $reg_id",
        reg_id=reg_id
    )
    
    # 1. Update Fact properties
    # Facts in the schema store `user_id` directly to bypass traversal overhead during unique constraints
    tx.run(
        "MATCH (f:Fact {user_id: $guest_id}) "
        "SET f.user_id = $reg_id",
        guest_id=guest_id,
        reg_id=reg_id
    )
    
    # 2. Re-wire edges from the Guest User node to the Registered User node
    # This covers: HAS_MEMORY, HAS_FACT, OWNS_SPACE, and derived relationships (LIVES_IN, WORKS_AT, KNOWS, PREFERS)
    
    # Let's do explicit edge rewiring for known schema edges.
    edge_types = ["HAS_MEMORY", "HAS_FACT", "OWNS_SPACE", "LIVES_IN", "WORKS_AT", "KNOWS", "PREFERS"]
    for e_type in edge_types:
        tx.run(f"""
            MATCH (guest:User {{id: $guest_id}})-[r:{e_type}]->(target)
            MATCH (reg:User {{id: $reg_id}})
            MERGE (reg)-[new_r:{e_type}]->(target)
            // Copy properties if any
            SET new_r += properties(r)
            DELETE r
        """, guest_id=guest_id, reg_id=reg_id)
        
    # 3. Finally, delete the Guest User node
    tx.run(
        "MATCH (guest:User {id: $guest_id}) DETACH DELETE guest",
        guest_id=guest_id
    )
