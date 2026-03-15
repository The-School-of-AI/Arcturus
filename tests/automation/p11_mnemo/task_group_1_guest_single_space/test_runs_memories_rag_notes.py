import pytest
from tests.automation.p11_mnemo.helpers import wait_for_condition
from memory.vector_store import get_vector_store
from memory.knowledge_graph import get_knowledge_graph
from memory.unified_extraction_schema import FactItem, UnifiedExtractionResult, MemoryCommand, EntityItem, EntityRelationshipItem
from memory.space_constants import SPACE_ID_GLOBAL

# Import whatever router/function creates runs. This might require app imports,
# but we can test the memory level first.
from routers.runs import create_run
from routers.runs import RunRequest
from routers.remme import add_memory
from routers.remme import AddMemoryRequest
from core.auth.context import set_current_user_id

@pytest.fixture(autouse=True)
def mock_mnemo_enabled(monkeypatch):
    monkeypatch.setenv("MNEMO_ENABLED", "true")

def _fact_value(driver, user_id: str, key: str = "location"):
    """Return Fact value_text for user_id and key, or None."""
    with driver.session() as session:
        result = session.run(
            "MATCH (u:User {user_id: $user_id})-[:HAS_FACT]->(f:Fact {key: $key}) RETURN f.value_text as val",
            user_id=user_id,
            key=key,
        )
        rec = result.single()
        return rec["val"] if rec else None


@pytest.fixture
def mock_guest_user():
    user = "00000000-0000-0000-0000-testguestuser1"
    set_current_user_id(user)
    return user

@pytest.mark.p11_automation
@pytest.mark.asyncio
async def test_tg1_01_create_sample_runs(mock_guest_user):
    # Verify we can get/create a run
    run_id = "test_run_123"
    session_info = await create_run(RunRequest(query="Test", space_id=SPACE_ID_GLOBAL, source="web", stream=False, dry_run=True), background_tasks=None)
    run_id = session_info["id"]
    
    # In some codebases the function returns different things, just check it succeeds
    kg = get_knowledge_graph()
    space = kg.get_space_for_session(run_id)
    assert space is None or space == SPACE_ID_GLOBAL

@pytest.mark.p11_automation
@pytest.mark.asyncio
async def test_tg1_02_add_memory_location(mock_guest_user, mock_llm_extractor, neo4j_test_driver):
    run_id = "test_run_123"
    
    # Configure the mock extractor
    mock_llm_extractor.mock_result = UnifiedExtractionResult(
        source="memory",
        memories=[MemoryCommand(action="add", text="I moved from New Jersey to Raleigh, NC last year.")],
        facts=[FactItem(field_id="location", value_type="text", value="Raleigh, NC", entity_ref="Concept::Raleigh")]
    )
    
    # Call create_memory
    mem_res = await add_memory(AddMemoryRequest(
        text="I moved from New Jersey to Raleigh, NC last year. I am loving it here as the weather is really great",
        space_id=SPACE_ID_GLOBAL
    ), background_tasks=None)
    wait_for_condition(
        lambda: len(get_vector_store().get_all(filter_metadata={"user_id": mock_guest_user, "space_id": SPACE_ID_GLOBAL}, limit=10)) > 0,
        timeout_sec=5.0,
    )
    assert "memory" in mem_res, f"Unexpected response: {mem_res}"
    mem_id = mem_res["memory"].get("id")
    assert mem_id is not None, f"Memory ID missing in {mem_res}"
    
    # Verify fact in Neo4j
    with neo4j_test_driver.session() as session:
        result = session.run(
            "MATCH (u:User {user_id: $user_id})-[:HAS_FACT]->(f:Fact {key: 'location'}) RETURN f.value_text as val",
            user_id=mock_guest_user
        )
        record = result.single()
        assert record is not None
        assert record["val"] == "Raleigh, NC"
    
    # Verify in Qdrant
    store = get_vector_store()
    memories = store.get_all(filter_metadata={"user_id": mock_guest_user, "space_id": SPACE_ID_GLOBAL}, limit=10)
    assert len(memories) > 0

@pytest.mark.p11_automation
@pytest.mark.asyncio
async def test_tg1_04_add_memory_entities(mock_guest_user, mock_llm_extractor, neo4j_test_driver):
    run_id = "test_run_124"
    mock_llm_extractor.mock_result = UnifiedExtractionResult(
        source="memory",
        memories=[MemoryCommand(action="add", text="My friend Jon recently moved from California to Durham. He works at Google.")],
        entities=[
            EntityItem(type="Person", name="Jon"),
            EntityItem(type="Organization", name="Google"),
            EntityItem(type="City", name="Durham")
        ],
        entity_relationships=[
            EntityRelationshipItem(from_type="Person", from_name="Jon", to_type="Organization", to_name="Google", type="WORKS_AT", confidence=1.0),
            EntityRelationshipItem(from_type="Person", from_name="Jon", to_type="City", to_name="Durham", type="LOCATED_IN", confidence=1.0)
        ]
    )
    
    mem_res = await add_memory(AddMemoryRequest(
        text="My friend Jon recently moved from California to Durham. He works at Google. He may need help settling down",
        space_id=SPACE_ID_GLOBAL
    ), background_tasks=None)
    mem_id = mem_res["memory"]["id"]
    # Wait for Neo4j to have the relationship (async ingest)
    def has_works_at():
        with neo4j_test_driver.session() as session:
            result = session.run(
                "MATCH (p:Entity {canonical_name: 'jon'})-[:WORKS_AT]->(c:Entity {canonical_name: 'google'}) RETURN p, c"
            )
            return result.single() is not None
    wait_for_condition(has_works_at, timeout_sec=5.0)
    
    # Verify Entities and relationships in Neo4j
    with neo4j_test_driver.session() as session:
        result = session.run(
            "MATCH (p:Entity {canonical_name: 'jon'})-[:WORKS_AT]->(c:Entity {canonical_name: 'google'}) RETURN p, c"
        )
        assert result.single() is not None, "WORKS_AT relationship missing"

@pytest.mark.p11_automation
@pytest.mark.asyncio
async def test_tg1_09_fact_superseding(mock_guest_user, mock_llm_extractor, neo4j_test_driver):
    # Setup initial fact
    mock_llm_extractor.mock_result = UnifiedExtractionResult(
        source="memory",
        memories=[MemoryCommand(action="add", text="I live in Raleigh")],
        facts=[FactItem(field_id="location", value_type="text", value="Raleigh", entity_ref="Concept::Raleigh")]
    )
    await add_memory(AddMemoryRequest(text="I live in Raleigh", space_id=SPACE_ID_GLOBAL), background_tasks=None)
    wait_for_condition(
        lambda: _fact_value(neo4j_test_driver, mock_guest_user) is not None,
        timeout_sec=5.0,
    )
    
    # Update fact
    mock_llm_extractor.mock_result = UnifiedExtractionResult(
        source="memory",
        memories=[MemoryCommand(action="add", text="I actually moved to Charlotte")],
        facts=[FactItem(field_id="location", value_type="text", value="Charlotte", entity_ref="Concept::Charlotte")]
    )
    await add_memory(AddMemoryRequest(text="I actually moved to Charlotte", space_id=SPACE_ID_GLOBAL), background_tasks=None)
    wait_for_condition(
        lambda: _fact_value(neo4j_test_driver, mock_guest_user) == "Charlotte",
        timeout_sec=5.0,
    )

    with neo4j_test_driver.session() as session:
        # Check active fact
        result = session.run(
            "MATCH (u:User {user_id: $user_id})-[:HAS_FACT]->(f:Fact {key: 'location'}) "
            "RETURN f.value_text as val",
            user_id=mock_guest_user
        )
        rec = result.single()
        assert rec is not None
        assert rec["val"] == "Charlotte"
