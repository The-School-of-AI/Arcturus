import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

import gateway_api.integration_tracing as integration_tracing_module
import gateway_api.idempotency as idempotency_module
import gateway_api.key_store as key_store_module
import gateway_api.metering as metering_module
import gateway_api.v1.agents as agents_routes
import gateway_api.v1.chat as chat_routes
import gateway_api.v1.cron as cron_routes
import gateway_api.v1.embeddings as embeddings_routes
import gateway_api.v1.memory as memory_routes
import gateway_api.v1.pages as pages_routes
import gateway_api.v1.search as search_routes
import gateway_api.v1.studio as studio_routes
import gateway_api.webhooks as webhooks_module
from core.gateway_services.exceptions import UpstreamIntegrationError
from core.scheduler import JobDefinition
from gateway_api.integration_tracing import IntegrationTracer
from gateway_api.idempotency import IdempotencyStore
from gateway_api.key_store import GatewayKeyStore
from gateway_api.metering import GatewayMeteringStore
from gateway_api.rate_limiter import InMemoryTokenBucketLimiter
from gateway_api.v1.router import router as gateway_router
from gateway_api.webhooks import WebhookService


class _FakeScheduler:
    def __init__(self):
        self.jobs = {}
        self.history = {}

    def list_jobs(self):
        return list(self.jobs.values())

    def add_job(
        self,
        name: str,
        cron_expression: str,
        agent_type: str,
        query: str,
        timezone: str = "UTC",
    ):
        job = JobDefinition(
            id=f"job_{len(self.jobs) + 1}",
            name=name,
            cron_expression=cron_expression,
            agent_type=agent_type,
            query=query,
            timezone=timezone,
        )
        self.jobs[job.id] = job
        self.history.setdefault(job.id, [])
        return job

    def trigger_job(self, job_id: str):
        if job_id not in self.jobs:
            raise KeyError(job_id)
        self.jobs[job_id].last_run = datetime.now(timezone.utc).isoformat()
        self.history.setdefault(job_id, []).append(
            {
                "job_id": job_id,
                "run_id": f"manual_{job_id}",
                "status": "success",
                "started_at": self.jobs[job_id].last_run,
                "finished_at": self.jobs[job_id].last_run,
                "error": None,
                "output_summary": "manual trigger",
            }
        )

    def delete_job(self, job_id: str):
        self.jobs.pop(job_id, None)

    def get_job_history(self, job_id: str, limit: int = 50):
        rows = list(self.history.get(job_id, []))
        rows = rows[-max(1, limit) :]
        rows.reverse()
        return rows


class _FakeOracleAdapter:
    def __init__(self, state: dict, fail: bool = False):
        self.state = state
        self.fail = fail

    async def search(self, query: str, limit: int = 5):
        self.state["oracle_calls"] += 1
        if self.fail:
            raise UpstreamIntegrationError("oracle unavailable")

        return {
            "status": "success",
            "query": query,
            "results": [
                {
                    "title": "Oracle Result",
                    "url": "https://oracle.example.com",
                    "content": f"oracle content for {query}",
                    "rank": 1,
                }
            ][:limit],
            "citations": ["https://oracle.example.com"],
            "summary": "oracle summary",
        }


class _FakeSparkAdapter:
    def __init__(self, state: dict, fail: bool = False):
        self.state = state
        self.fail = fail

    async def generate_page(self, query: str, template: str | None, oracle_context: dict | None):
        self.state["spark_calls"] += 1
        if self.fail:
            raise UpstreamIntegrationError("spark generation failed")

        return {
            "page_id": "page_runtime_1",
            "query": query,
            "template": template,
            "title": "Runtime Page",
            "summary": "runtime spark summary",
            "artifact": {
                "name": "Runtime Page",
                "theme": {"colors": {"primary": "#224488"}},
                "pages": [{"path": "/", "components": []}],
            },
            "citations": list((oracle_context or {}).get("citations", [])),
        }


class _FakeForgeAdapter:
    def __init__(self, state: dict, fail: bool = False):
        self.state = state
        self.fail = fail

    async def generate_outline(
        self,
        prompt: str,
        artifact_type: str,
        template: str | None,
        oracle_context: dict | None,
    ):
        del prompt, template
        self.state["forge_calls"] += 1
        if self.fail:
            raise UpstreamIntegrationError("forge outline failed")

        return {
            "artifact_id": f"artifact_{artifact_type}_1",
            "artifact_type": artifact_type,
            "title": f"{artifact_type.title()} Outline",
            "status": "pending",
            "outline": {
                "artifact_type": artifact_type,
                "title": f"{artifact_type.title()} Outline",
                "items": [{"id": "1", "title": "Section", "children": []}],
                "status": "pending",
            },
            "citations": list((oracle_context or {}).get("citations", [])),
        }


def build_gateway_runtime_context(
    tmp_path,
    monkeypatch,
    *,
    oracle_fail: bool = False,
    spark_fail: bool = False,
    forge_fail: bool = False,
):
    state = {"oracle_calls": 0, "spark_calls": 0, "forge_calls": 0}

    keys_file = tmp_path / "api_keys.json"
    audit_file = tmp_path / "key_audit.jsonl"
    events_file = tmp_path / "metering_events.jsonl"
    integration_events = tmp_path / "integration_events.jsonl"
    idempotency_records = tmp_path / "idempotency_records.json"

    key_store = GatewayKeyStore(keys_file=keys_file, audit_file=audit_file)
    metering_store = GatewayMeteringStore(events_file=events_file, data_dir=tmp_path)
    idempotency_store = IdempotencyStore(records_file=idempotency_records)

    monkeypatch.setattr(key_store_module, "_gateway_key_store", key_store)
    monkeypatch.setattr(metering_module, "_metering_store", metering_store)
    monkeypatch.setattr(idempotency_module, "_idempotency_store", idempotency_store)
    monkeypatch.setattr(
        integration_tracing_module,
        "_integration_tracer",
        IntegrationTracer(events_file=integration_events),
    )
    monkeypatch.setattr("gateway_api.rate_limiter.limiter", InMemoryTokenBucketLimiter())

    async def _fake_search(query: str, limit: int = 5):
        return {
            "status": "success",
            "results": [
                {
                    "title": "Result",
                    "url": "https://example.com",
                    "content": f"answer for {query}",
                    "rank": 1,
                }
            ][:limit],
        }

    async def _fake_process_run(run_id: str, query: str):
        return {
            "status": "completed",
            "run_id": run_id,
            "output": f"processed: {query}",
            "summary": f"processed: {query}",
        }

    async def _fake_embeddings(inputs, model=None):
        return {
            "object": "list",
            "model": model or "fake-embed",
            "data": [
                {"object": "embedding", "index": idx, "embedding": [0.1, 0.2, 0.3]}
                for idx, _ in enumerate(inputs)
            ],
            "usage": {"prompt_tokens": len(inputs), "total_tokens": len(inputs)},
        }

    async def _fake_read_memories(category=None, limit=10):  # noqa: ARG001
        return {
            "status": "success",
            "count": 1,
            "memories": [
                {
                    "id": "mem_1",
                    "text": "stored memory",
                    "category": category or "general",
                    "source": "test",
                    "score": 0.1,
                }
            ][:limit],
        }

    async def _fake_write_memory(text: str, source: str, category: str):
        return {
            "status": "success",
            "memory": {
                "id": "mem_new",
                "text": text,
                "source": source,
                "category": category,
            },
        }

    async def _fake_search_memories(query: str, limit=5):  # noqa: ARG001
        return {
            "status": "success",
            "count": 1,
            "memories": [
                {
                    "id": "mem_search",
                    "text": "match",
                    "category": "general",
                    "source": "test",
                    "score": 0.05,
                }
            ][:limit],
        }

    monkeypatch.setattr(search_routes, "web_search", _fake_search)
    monkeypatch.setattr(chat_routes, "process_run", _fake_process_run)
    monkeypatch.setattr(agents_routes, "process_run", _fake_process_run)
    monkeypatch.setattr(embeddings_routes, "create_embeddings", _fake_embeddings)
    monkeypatch.setattr(memory_routes, "service_read_memories", _fake_read_memories)
    monkeypatch.setattr(memory_routes, "service_write_memory", _fake_write_memory)
    monkeypatch.setattr(memory_routes, "service_search_memories", _fake_search_memories)

    oracle_adapter = _FakeOracleAdapter(state, fail=oracle_fail)
    spark_adapter = _FakeSparkAdapter(state, fail=spark_fail)
    forge_adapter = _FakeForgeAdapter(state, fail=forge_fail)
    monkeypatch.setattr(pages_routes, "get_oracle_adapter", lambda: oracle_adapter)
    monkeypatch.setattr(pages_routes, "get_spark_adapter", lambda: spark_adapter)
    monkeypatch.setattr(studio_routes, "get_oracle_adapter", lambda: oracle_adapter)
    monkeypatch.setattr(studio_routes, "get_forge_adapter", lambda: forge_adapter)

    fake_scheduler = _FakeScheduler()
    monkeypatch.setattr(cron_routes, "scheduler_service", fake_scheduler)

    webhook_service = WebhookService(
        subscriptions_file=tmp_path / "webhook_subscriptions.json",
        deliveries_file=tmp_path / "webhook_deliveries.jsonl",
        dlq_file=tmp_path / "webhook_dlq.jsonl",
    )
    monkeypatch.setattr(webhooks_module, "_webhook_service", webhook_service)
    monkeypatch.setenv("ARCTURUS_GATEWAY_GITHUB_WEBHOOK_SECRET", "runtime-github-secret")
    monkeypatch.setenv("ARCTURUS_GATEWAY_JIRA_WEBHOOK_TOKEN", "runtime-jira-token")
    monkeypatch.setenv("ARCTURUS_GATEWAY_GMAIL_CHANNEL_TOKEN", "runtime-gmail-token")

    app = FastAPI()
    app.include_router(gateway_router)
    client = TestClient(app)

    def create_api_key(
        scopes,
        rpm_limit=120,
        burst_limit=60,
        monthly_request_quota=100_000,
        monthly_unit_quota=500_000,
    ):
        _, plaintext = asyncio.run(
            key_store.create_key(
                name="runtime-test",
                scopes=scopes,
                rpm_limit=rpm_limit,
                burst_limit=burst_limit,
                monthly_request_quota=monthly_request_quota,
                monthly_unit_quota=monthly_unit_quota,
            )
        )
        return plaintext

    def connector_headers(source: str, payload: dict, *, event_name: str | None = None) -> dict:
        source_key = source.strip().lower()
        body = json.dumps(payload)
        delivery_id = f"runtime-{hashlib.sha256(body.encode('utf-8')).hexdigest()[:12]}"
        if source_key == "github":
            signature = "sha256=" + hmac.new(
                b"runtime-github-secret",
                body.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            return {
                "content-type": "application/json",
                "x-github-event": event_name or "push",
                "x-github-delivery": delivery_id,
                "x-hub-signature-256": signature,
            }
        if source_key == "jira":
            return {
                "content-type": "application/json",
                "x-atlassian-webhook-token": "runtime-jira-token",
            }
        if source_key == "gmail":
            return {
                "content-type": "application/json",
                "x-goog-channel-token": "runtime-gmail-token",
                "x-goog-message-number": "1001",
            }
        raise ValueError(f"Unsupported connector source: {source_key}")

    return {
        "client": client,
        "create_api_key": create_api_key,
        "webhook_service": webhook_service,
        "integration_events": integration_events,
        "connector_headers": connector_headers,
        "state": state,
    }
