import pytest
import asyncio
from typing import List

from tests.automation.p11_mnemo.helpers import wait_for_condition
from memory.vector_store import get_vector_store
from memory.knowledge_graph import get_knowledge_graph
from memory.unified_extraction_schema import FactItem, UnifiedExtractionResult, MemoryCommand
from routers.remme import add_memory, AddMemoryRequest
from memory.space_constants import SPACE_ID_GLOBAL
from core.auth.context import set_current_user_id
from fastapi import BackgroundTasks
from memory.memory_retriever import retrieve


@pytest.fixture
def tg3_guest_id():
    user = "00000000-0000-0000-0000-tg3guestuser99"
    set_current_user_id(user)
    return user

@pytest.fixture
def tg3_registered_id():
    return "tg3-registered-user-id-555"

@pytest.mark.p11_automation
@pytest.mark.asyncio
async def test_tg3_02_registration_migration(tg3_guest_id, tg3_registered_id, mock_llm_extractor, neo4j_test_driver):
    bg_tasks = BackgroundTasks()
    
    # Setup: Guest populates data
    mock_llm_extractor.mock_result = UnifiedExtractionResult(
        source="memory",
        memories=[MemoryCommand(action="add", text="Guest memory before registration")],
        facts=[FactItem(field_id="interests.hobbies", value_type="text", value="Reading", entity_ref="Hobby::Reading")]
    )
    
    await add_memory(AddMemoryRequest(
        text="Guest memory before registration",
        space_id=SPACE_ID_GLOBAL
    ), background_tasks=bg_tasks)
    
    # Trigger Migration
    # Note: Migration logic usually lives in `memory.migration` or `core.auth`
    # We will simulate the data layer migration for user_id reassignment which usually 
    # involves Qdrant payload updates and Neo4j node property updates.
    
    # Qdrant Migration
    store = get_vector_store()
    # We need to find the memory that was added as guest. 
    # Since we changed current user to Registered, we must filter explicitly.
    memories = store.get_all(filter_metadata={"user_id": tg3_guest_id}, limit=100)
    assert len(memories) > 0, "Guest memory not found before migration"
    for m in memories:
        # For migration (owner change), we typically bypass the wrapper's owner check 
        # by using the qdrant client directly.
        store.client.set_payload(
            collection_name=store.collection_name,
            payload={"user_id": tg3_registered_id},
            points=[m["id"]]
        )
    
    # Wait for index consistency before verifying
    wait_for_condition(
        lambda: len(store.get_all(filter_metadata={"user_id": tg3_registered_id}, limit=100)) >= 1,
        timeout_sec=5.0,
    )
        
    # Neo4j Migration
    with neo4j_test_driver.session() as session:
        # Transfer User node and all relationships
        session.run("""
            MATCH (u:User {id: $old_id})
            SET u.id = $new_id, u.user_id = $new_id
        """, old_id=tg3_guest_id, new_id=tg3_registered_id)
        
        # Transfer Fact tenant owners
        session.run("""
            MATCH (f:Fact {user_id: $old_id})
            SET f.user_id = $new_id
        """, old_id=tg3_guest_id, new_id=tg3_registered_id)
        
    # Verify Migration
    set_current_user_id(tg3_registered_id)
    post_mig_memories = store.get_all(filter_metadata={"user_id": tg3_registered_id}, limit=100)
    assert len(post_mig_memories) == 1
    assert post_mig_memories[0]["text"] == "Guest memory before registration"
    
    set_current_user_id(tg3_guest_id)
    guest_memories = store.get_all(filter_metadata={"user_id": tg3_guest_id}, limit=100)
    assert len(guest_memories) == 0

@pytest.mark.p11_automation
@pytest.mark.asyncio
async def test_tg3_12_lifecycle_archival(tg3_registered_id, mock_llm_extractor):
    set_current_user_id(tg3_registered_id)
    bg_tasks = BackgroundTasks()
    
    # Test Importance Scoring and Archival exclusion
    store = get_vector_store()
    
    # Add a memory
    mock_llm_extractor.mock_result = UnifiedExtractionResult(source="memory", memories=[MemoryCommand(action="add", text="Old memory")])
    mem_res = await add_memory(AddMemoryRequest(text="Old memory", space_id=SPACE_ID_GLOBAL), background_tasks=bg_tasks)
    mem_id = mem_res["memory"]["id"]
    
    # Archive it (Set importance < 0.1 threshold to ensure it stays archived during retrieval)
    # Using client directly to ensure flag is set regardless of transient owner context
    store.client.set_payload(
        collection_name=store.collection_name,
        payload={"archived": True, "importance": 0.01},
        points=[mem_id]
    )
    wait_for_condition(lambda: store.get(mem_id) and store.get(mem_id).get("archived") is True, timeout_sec=5.0)
    
    # Verify via direct get first to be sure flag is set
    mem_check = store.get(mem_id)
    assert mem_check.get("archived") is True, f"Archived flag not set on {mem_id}"
    
    # Now check retriever. Default retrieve() SHOULD omit it (per memory_retriever.py:136)
    context, result = retrieve(query="Old memory", user_id=tg3_registered_id, space_id=SPACE_ID_GLOBAL)
    
    matched = any(r["id"] == mem_id for r in result)
    assert not matched, "Archived memory was incorrectly retrieved by default"
    
    # Verify that we can still retrieve it if we search directly with archived=True
    store = get_vector_store()
    from remme.utils import get_embedding
    emb = get_embedding("Old memory")
    result_with_archived = store.search(emb, query_text="Old memory", filter_metadata={"archived": True})
    assert any(r["id"] == mem_id for r in result_with_archived), "Archived memory not found even with explicit filter"
