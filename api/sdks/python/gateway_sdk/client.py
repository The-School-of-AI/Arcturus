from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import httpx


@dataclass
class GatewayResponseMetadata:
    idempotency_status: str | None
    idempotency_key: str | None
    usage_headers: Dict[str, str]
    rate_limit_headers: Dict[str, str]


@dataclass
class GatewayResult:
    status_code: int
    body: Any
    metadata: GatewayResponseMetadata


class GatewayAPIError(RuntimeError):
    def __init__(self, status_code: int, body: Any) -> None:
        self.status_code = status_code
        self.body = body
        error = body.get("detail", body) if isinstance(body, dict) else body
        message = str(error)
        super().__init__(f"Gateway API error ({status_code}): {message}")


class GatewayClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        admin_key: str | None = None,
        timeout: float = 30.0,
        idempotency_key_factory: Optional[Callable[[], str]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.admin_key = admin_key
        self.idempotency_key_factory = idempotency_key_factory or (lambda: f"sdk-{uuid.uuid4().hex}")
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "GatewayClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        del exc_type, exc_val, exc_tb
        self.close()

    def _headers(
        self,
        *,
        auth_mode: str,
        mutating: bool,
        idempotency_key: str | None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        headers: Dict[str, str] = {"content-type": "application/json"}
        if auth_mode == "api":
            if not self.api_key:
                raise ValueError("api_key is required for this request")
            headers["x-api-key"] = self.api_key
        elif auth_mode == "admin":
            if not self.admin_key:
                raise ValueError("admin_key is required for this request")
            headers["x-gateway-admin-key"] = self.admin_key

        if mutating:
            headers["Idempotency-Key"] = idempotency_key or self.idempotency_key_factory()

        if extra_headers:
            headers.update(extra_headers)

        return headers

    def _metadata(self, response: httpx.Response) -> GatewayResponseMetadata:
        usage = {k: v for k, v in response.headers.items() if k.lower().startswith("x-usage-")}
        rate = {k: v for k, v in response.headers.items() if k.lower().startswith("x-ratelimit-")}
        return GatewayResponseMetadata(
            idempotency_status=response.headers.get("X-Idempotency-Status"),
            idempotency_key=response.headers.get("X-Idempotency-Key"),
            usage_headers=usage,
            rate_limit_headers=rate,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        auth_mode: str,
        mutating: bool = False,
        idempotency_key: str | None = None,
        json_body: Any = None,
        params: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> GatewayResult:
        response = self._client.request(
            method=method,
            url=f"{self.base_url}{path}",
            headers=self._headers(
                auth_mode=auth_mode,
                mutating=mutating,
                idempotency_key=idempotency_key,
                extra_headers=extra_headers,
            ),
            json=json_body,
            params=params,
        )
        body = response.json() if response.content else {}
        if response.status_code >= 400:
            raise GatewayAPIError(response.status_code, body)
        return GatewayResult(
            status_code=response.status_code,
            body=body,
            metadata=self._metadata(response),
        )

    # Public API
    def search(self, query: str, limit: int = 5) -> GatewayResult:
        return self._request("POST", "/api/v1/search", auth_mode="api", json_body={"query": query, "limit": limit})

    def chat_completions(self, messages: list[dict[str, str]], model: str | None = None, stream: bool = False) -> GatewayResult:
        payload: dict[str, Any] = {"messages": messages, "stream": stream}
        if model:
            payload["model"] = model
        return self._request("POST", "/api/v1/chat/completions", auth_mode="api", json_body=payload)

    def embeddings(self, input_value: str | list[str], model: str | None = None) -> GatewayResult:
        payload: dict[str, Any] = {"input": input_value}
        if model:
            payload["model"] = model
        return self._request("POST", "/api/v1/embeddings", auth_mode="api", json_body=payload)

    def memory_read(self, category: str | None = None, limit: int = 10) -> GatewayResult:
        payload: dict[str, Any] = {"limit": limit}
        if category is not None:
            payload["category"] = category
        return self._request("POST", "/api/v1/memory/read", auth_mode="api", json_body=payload)

    def memory_search(self, query: str, limit: int = 5) -> GatewayResult:
        return self._request("POST", "/api/v1/memory/search", auth_mode="api", json_body={"query": query, "limit": limit})

    def memory_write(self, text: str, source: str = "sdk", category: str = "general", idempotency_key: str | None = None) -> GatewayResult:
        return self._request(
            "POST",
            "/api/v1/memory/write",
            auth_mode="api",
            mutating=True,
            idempotency_key=idempotency_key,
            json_body={"text": text, "source": source, "category": category},
        )

    def agents_run(self, query: str, wait_for_completion: bool = True, idempotency_key: str | None = None) -> GatewayResult:
        return self._request(
            "POST",
            "/api/v1/agents/run",
            auth_mode="api",
            mutating=True,
            idempotency_key=idempotency_key,
            json_body={"query": query, "wait_for_completion": wait_for_completion},
        )

    def pages_generate(self, query: str, template: str | None = None, idempotency_key: str | None = None) -> GatewayResult:
        payload: dict[str, Any] = {"query": query}
        if template:
            payload["template"] = template
        return self._request(
            "POST",
            "/api/v1/pages/generate",
            auth_mode="api",
            mutating=True,
            idempotency_key=idempotency_key,
            json_body=payload,
        )

    def studio_generate(self, kind: str, prompt: str, template: str | None = None, idempotency_key: str | None = None) -> GatewayResult:
        payload: dict[str, Any] = {"prompt": prompt}
        if template:
            payload["template"] = template
        return self._request(
            "POST",
            f"/api/v1/studio/{kind}",
            auth_mode="api",
            mutating=True,
            idempotency_key=idempotency_key,
            json_body=payload,
        )

    def cron_jobs(self) -> GatewayResult:
        return self._request("GET", "/api/v1/cron/jobs", auth_mode="api")

    def cron_create_job(self, payload: Dict[str, Any], idempotency_key: str | None = None) -> GatewayResult:
        return self._request(
            "POST",
            "/api/v1/cron/jobs",
            auth_mode="api",
            mutating=True,
            idempotency_key=idempotency_key,
            json_body=payload,
        )

    def cron_trigger_job(self, job_id: str, idempotency_key: str | None = None) -> GatewayResult:
        return self._request(
            "POST",
            f"/api/v1/cron/jobs/{job_id}/trigger",
            auth_mode="api",
            mutating=True,
            idempotency_key=idempotency_key,
        )

    def cron_delete_job(self, job_id: str, idempotency_key: str | None = None) -> GatewayResult:
        return self._request(
            "DELETE",
            f"/api/v1/cron/jobs/{job_id}",
            auth_mode="api",
            mutating=True,
            idempotency_key=idempotency_key,
        )

    def cron_job_history(self, job_id: str, limit: int = 50) -> GatewayResult:
        return self._request(
            "GET",
            f"/api/v1/cron/jobs/{job_id}/history",
            auth_mode="api",
            params={"limit": limit},
        )

    def webhooks_list_connectors(self) -> GatewayResult:
        return self._request("GET", "/api/v1/webhooks/connectors", auth_mode="api")

    def webhooks_list(self) -> GatewayResult:
        return self._request("GET", "/api/v1/webhooks", auth_mode="api")

    def webhooks_create(self, payload: Dict[str, Any], idempotency_key: str | None = None) -> GatewayResult:
        return self._request(
            "POST",
            "/api/v1/webhooks",
            auth_mode="api",
            mutating=True,
            idempotency_key=idempotency_key,
            json_body=payload,
        )

    def webhooks_delete(self, subscription_id: str, idempotency_key: str | None = None) -> GatewayResult:
        return self._request(
            "DELETE",
            f"/api/v1/webhooks/{subscription_id}",
            auth_mode="api",
            mutating=True,
            idempotency_key=idempotency_key,
        )

    def webhooks_trigger(self, payload: Dict[str, Any], idempotency_key: str | None = None) -> GatewayResult:
        return self._request(
            "POST",
            "/api/v1/webhooks/trigger",
            auth_mode="api",
            mutating=True,
            idempotency_key=idempotency_key,
            json_body=payload,
        )

    def webhooks_dispatch(self, payload: Dict[str, Any], idempotency_key: str | None = None) -> GatewayResult:
        return self._request(
            "POST",
            "/api/v1/webhooks/dispatch",
            auth_mode="api",
            mutating=True,
            idempotency_key=idempotency_key,
            json_body=payload,
        )

    def webhooks_deliveries(self, status: str | None = None, limit: int = 100) -> GatewayResult:
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        return self._request("GET", "/api/v1/webhooks/deliveries", auth_mode="api", params=params)

    def webhooks_replay_dead_letter(self, delivery_id: str, idempotency_key: str | None = None) -> GatewayResult:
        return self._request(
            "POST",
            f"/api/v1/webhooks/dlq/{delivery_id}/replay",
            auth_mode="api",
            mutating=True,
            idempotency_key=idempotency_key,
        )

    def webhooks_inbound(
        self,
        source: str,
        payload: Dict[str, Any],
        *,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> GatewayResult:
        # Inbound endpoint does not require x-api-key; auth is signature/token-based.
        return self._request(
            "POST",
            f"/api/v1/webhooks/inbound/{source}",
            auth_mode="none",
            json_body=payload,
            extra_headers=extra_headers,
        )

    def usage_me(self, month: str | None = None) -> GatewayResult:
        params = {"month": month} if month else None
        return self._request("GET", "/api/v1/usage", auth_mode="api", params=params)

    def usage_all(self, month: str | None = None) -> GatewayResult:
        params = {"month": month} if month else None
        return self._request("GET", "/api/v1/usage/all", auth_mode="admin", params=params)

    # Admin key APIs
    def admin_list_keys(self, include_revoked: bool = False) -> GatewayResult:
        return self._request(
            "GET",
            "/api/v1/keys",
            auth_mode="admin",
            params={"include_revoked": str(include_revoked).lower()},
        )

    def admin_create_key(self, payload: Dict[str, Any], idempotency_key: str | None = None) -> GatewayResult:
        return self._request(
            "POST",
            "/api/v1/keys",
            auth_mode="admin",
            mutating=True,
            idempotency_key=idempotency_key,
            json_body=payload,
        )

    def admin_update_key(self, key_id: str, payload: Dict[str, Any], idempotency_key: str | None = None) -> GatewayResult:
        return self._request(
            "PATCH",
            f"/api/v1/keys/{key_id}",
            auth_mode="admin",
            mutating=True,
            idempotency_key=idempotency_key,
            json_body=payload,
        )

    def admin_rotate_key(self, key_id: str, idempotency_key: str | None = None) -> GatewayResult:
        return self._request(
            "POST",
            f"/api/v1/keys/{key_id}/rotate",
            auth_mode="admin",
            mutating=True,
            idempotency_key=idempotency_key,
        )

    def admin_revoke_key(self, key_id: str, idempotency_key: str | None = None) -> GatewayResult:
        return self._request(
            "DELETE",
            f"/api/v1/keys/{key_id}",
            auth_mode="admin",
            mutating=True,
            idempotency_key=idempotency_key,
        )
