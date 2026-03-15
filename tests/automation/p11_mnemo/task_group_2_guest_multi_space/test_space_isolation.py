import pytest
from memory.vector_store import get_vector_store
from memory.knowledge_graph import get_knowledge_graph
from memory.unified_extraction_schema import FactItem, UnifiedExtractionResult, MemoryCommand, EntityItem
from routers.remme import create_space, add_memory, CreateSpaceRequest, AddMemoryRequest
from memory.memory_retriever import retrieve
from memory.space_constants import SPACE_ID_GLOBAL
from core.auth.context import set_current_user_id
from fastapi import BackgroundTasks

@pytest.fixture
def tg2_guest_user():
    user = "00000000-0000-0000-0000-tg2guestuser99"
    set_current_user_id(user)
    return user

@pytest.mark.p11_automation
@pytest.mark.asyncio
async def test_tg2_01_space_creation_and_isolation(tg2_guest_user, mock_llm_extractor, neo4j_test_driver):
    bg_tasks = BackgroundTasks()
    
    # 1. Create spaces
    cat_res = await create_space(CreateSpaceRequest(name="Cat", description="Cats", sync_policy="local_only"), background_tasks=bg_tasks)
    cat_space_id = cat_res["space_id"]
    tech_res = await create_space(CreateSpaceRequest(name="Tech", description="Tech", sync_policy="local_only"), background_tasks=bg_tasks)
    tech_space_id = tech_res["space_id"]
    
    assert cat_space_id is not None
    assert tech_space_id is not None
    
    # 2. Add Cat memory
    mock_llm_extractor.mock_result = UnifiedExtractionResult(
        source="memory",
        memories=[MemoryCommand(action="add", text="My cat Luna loves tuna")],
        entities=[EntityItem(type="Animal", name="Luna")]
    )
    
    await add_memory(AddMemoryRequest(
        text="My cat Luna loves tuna",
        space_id=cat_space_id
    ), background_tasks=bg_tasks)

    # 3. Add Tech memory
    mock_llm_extractor.mock_result = UnifiedExtractionResult(
        source="memory",
        memories=[MemoryCommand(action="add", text="Planning to repaint the living room blue")],
        entities=[EntityItem(type="Concept", name="Living Room")]
    )
    
    await add_memory(AddMemoryRequest(
        text="Planning to repaint the living room blue",
        space_id=tech_space_id
    ), background_tasks=bg_tasks)
    
    # 4. Run in Tech space: "What do I know about Luna?"
    # We should NOT retrieve the Cat memory
    # First, configure the unified extractor for the retrieval query extracting 'Luna'
    from memory.entity_extractor import EntityExtractor
    
    # Mock EntityExtractor for query side
    class MockEntityExtractor(EntityExtractor):
        def extract_from_query(self, query: str):
            if "Luna" in query:
                return [EntityItem(type="Animal", name="Luna")]
            return []
    
    # Patch retriever entity extractor logic
    from unittest.mock import patch
    
    with patch("memory.entity_extractor.EntityExtractor", MockEntityExtractor):
        try:
            context, results = retrieve(query="What do I know about Luna?", user_id=tg2_guest_user, space_id=tech_space_id)
            
            # Verify isolation: Tech space should not surface Luna from Cat space
            for res in results:
                assert "Luna" not in res["text"], "Isolation failed: Cat memory leaked into Tech space"
                
            context_cat, results_cat = retrieve(query="What do I know about Luna?", user_id=tg2_guest_user, space_id=cat_space_id)
            
            found = any("Luna" in res["text"] for res in results_cat)
            assert found, "Cat memory not found in Cat space"
        finally:
            pass
    # mr.EntityExtractor patching removed since we use context manager now
