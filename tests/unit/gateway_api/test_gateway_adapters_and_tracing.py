import asyncio

from core.gateway_services.forge_adapter import ForgeAdapter
from core.gateway_services.oracle_adapter import OracleAdapter
from core.gateway_services.spark_adapter import SparkAdapter
from gateway_api.integration_tracing import IntegrationTracer


def test_oracle_adapter_maps_search_results_to_citations(monkeypatch):
    async def _fake_web_search(query: str, limit: int = 5):
        return {
            "status": "success",
            "summary": f"summary {query}",
            "results": [
                {"url": "https://a.example", "title": "A", "content": "alpha", "rank": 1},
                {"url": "", "title": "B", "content": "beta", "rank": 2},
            ][:limit],
        }

    monkeypatch.setattr("core.gateway_services.oracle_adapter.web_search", _fake_web_search)

    result = asyncio.run(OracleAdapter().search("query", limit=5))

    assert result["status"] == "success"
    assert result["summary"] == "summary query"
    assert result["citations"] == ["https://a.example"]


def test_spark_adapter_uses_appgenerator_and_returns_structured_page(monkeypatch):
    class _FakeGenerator:
        def __init__(self, project_root=None):
            self.project_root = project_root

        async def generate_frontend(self, prompt: str):
            return {
                "name": "Spark Page",
                "theme": {"colors": {"primary": "#123456"}},
                "pages": [{"path": "/", "components": [{"id": "c1", "type": "hero"}]}],
                "_prompt": prompt,
            }

    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr("core.gateway_services.spark_adapter.AppGenerator", _FakeGenerator)

    result = asyncio.run(
        SparkAdapter().generate_page(
            query="Build AI landscape page",
            template="overview",
            oracle_context={"citations": ["https://a.example"]},
        )
    )

    assert result["page_id"].startswith("page_")
    assert result["title"] == "Spark Page"
    assert result["citations"] == ["https://a.example"]
    assert result["artifact"]["name"] == "Spark Page"


def test_forge_adapter_maps_docs_to_document_artifact_type(monkeypatch):
    class _FakeOrchestrator:
        def __init__(self, storage):
            self.storage = storage

        async def generate_outline(self, prompt, artifact_type, parameters):
            return {
                "artifact_id": "artifact_123",
                "status": "pending",
                "outline": {
                    "artifact_type": artifact_type.value,
                    "title": "Quarterly Plan",
                    "items": [{"id": "i1", "title": "Overview", "children": []}],
                    "parameters": parameters,
                },
            }

    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr("core.gateway_services.forge_adapter.ForgeOrchestrator", _FakeOrchestrator)
    monkeypatch.setattr("core.gateway_services.forge_adapter.get_studio_storage", lambda: object())

    result = asyncio.run(
        ForgeAdapter().generate_outline(
            prompt="Create enterprise architecture document",
            artifact_type="document",
            template="technical",
            oracle_context={"citations": ["https://oracle.example"]},
        )
    )

    assert result["artifact_id"] == "artifact_123"
    assert result["artifact_type"] == "document"
    assert result["outline"]["artifact_type"] == "document"
    assert result["citations"] == ["https://oracle.example"]


def test_integration_tracing_writes_stage_events_with_trace_id(tmp_path):
    events_file = tmp_path / "integration_events.jsonl"
    tracer = IntegrationTracer(events_file=events_file)

    asyncio.run(
        tracer.record(
            trace_id="trc_test",
            flow="oracle_search",
            stage="search",
            status="success",
            context={"count": 1},
        )
    )
    asyncio.run(
        tracer.record(
            trace_id="trc_test",
            flow="spark_page_generation",
            stage="generate",
            status="success",
            context={"page_id": "p1"},
        )
    )

    rows = asyncio.run(tracer.list_events(trace_id="trc_test"))
    assert len(rows) == 2
    assert rows[0]["trace_id"] == "trc_test"
    assert rows[1]["flow"] == "spark_page_generation"
