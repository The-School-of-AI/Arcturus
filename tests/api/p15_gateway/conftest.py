import asyncio
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import gateway_api.key_store as key_store_module
import gateway_api.metering as metering_module
import gateway_api.v1.agents as agents_routes
import gateway_api.v1.chat as chat_routes
import gateway_api.v1.cron as cron_routes
import gateway_api.v1.embeddings as embeddings_routes
import gateway_api.v1.memory as memory_routes
import gateway_api.v1.search as search_routes
import gateway_api.webhooks as webhooks_module
from core.scheduler import JobDefinition
from gateway_api.key_store import GatewayKeyStore
from gateway_api.metering import GatewayMeteringStore
from gateway_api.v1.router import router as gateway_router
from gateway_api.webhooks import WebhookService


class _FakeScheduler:
    def __init__(self):
        self.jobs = {}

    def list_jobs(self):
        return list(self.jobs.values())

    def add_job(self, name: str, cron_expression: str, agent_type: str, query: str):
        job = JobDefinition(
            id=f"job_{len(self.jobs) + 1}",
            name=name,
            cron_expression=cron_expression,
            agent_type=agent_type,
            query=query,
        )
        self.jobs[job.id] = job
        return job

    def trigger_job(self, job_id: str):
        if job_id not in self.jobs:
            raise KeyError(job_id)
        self.jobs[job_id].last_run = datetime.now(timezone.utc).isoformat()

    def delete_job(self, job_id: str):
        self.jobs.pop(job_id, None)


@pytest.fixture()
def gateway_test_client(tmp_path, monkeypatch):
    keys_file = tmp_path / "api_keys.json"
    audit_file = tmp_path / "key_audit.jsonl"
    events_file = tmp_path / "metering_events.jsonl"

    key_store = GatewayKeyStore(keys_file=keys_file, audit_file=audit_file)
    metering_store = GatewayMeteringStore(events_file=events_file, data_dir=tmp_path)

    monkeypatch.setattr(key_store_module, "_gateway_key_store", key_store)
    monkeypatch.setattr(metering_module, "_metering_store", metering_store)

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

    fake_scheduler = _FakeScheduler()
    monkeypatch.setattr(cron_routes, "scheduler_service", fake_scheduler)

    subscriptions_file = tmp_path / "webhook_subscriptions.json"
    monkeypatch.setattr(webhooks_module, "WEBHOOK_DELIVERIES_FILE", tmp_path / "webhook_deliveries.jsonl")
    monkeypatch.setattr(webhooks_module, "WEBHOOK_DLQ_FILE", tmp_path / "webhook_dlq.jsonl")
    monkeypatch.setattr(webhooks_module, "_webhook_service", WebhookService(subscriptions_file))

    app = FastAPI()
    app.include_router(gateway_router)
    client = TestClient(app)

    def create_api_key(scopes):
        _, plaintext = asyncio.run(
            key_store.create_key(
                name="test",
                scopes=scopes,
                rpm_limit=120,
                burst_limit=60,
            )
        )
        return plaintext

    return client, create_api_key
