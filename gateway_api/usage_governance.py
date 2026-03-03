from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, Request, Response, status

from gateway_api.auth import AuthContext
from gateway_api.metering import get_metering_store

DEFAULT_MONTHLY_REQUEST_QUOTA = 100_000
DEFAULT_MONTHLY_UNIT_QUOTA = 500_000


@dataclass
class UsageGovernanceDecision:
    month: str
    request_limit: int
    request_remaining: int
    unit_limit: int
    unit_remaining: int
    estimated_units: int



def _month_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _error_payload(code: str, message: str, details: Optional[dict] = None) -> dict:
    payload = {"code": code, "message": message}
    if details:
        payload["details"] = details
    return {"error": payload}


def estimate_request_units(method: str, path: str) -> int:
    method_upper = method.upper()

    if method_upper == "POST" and path.startswith("/api/v1/studio/"):
        return 5
    if method_upper == "POST" and path == "/api/v1/pages/generate":
        return 5

    if method_upper == "POST" and path == "/api/v1/agents/run":
        return 3

    if path.startswith("/api/v1/chat/"):
        return 2
    if method_upper == "POST" and path == "/api/v1/embeddings":
        return 2

    if path == "/api/v1/memory/write" and method_upper == "POST":
        return 2

    if path.startswith("/api/v1/cron/") and method_upper in {"POST", "PUT", "PATCH", "DELETE"}:
        return 2

    if method_upper == "DELETE" and path.startswith("/api/v1/webhooks/"):
        return 2
    if method_upper == "POST" and (
        path == "/api/v1/webhooks/dispatch"
        or path == "/api/v1/webhooks/trigger"
        or path.startswith("/api/v1/webhooks/dlq/")
        or path == "/api/v1/webhooks"
    ):
        return 2

    if path.startswith("/api/v1/keys") and method_upper in {"POST", "PATCH", "DELETE"}:
        return 2

    return 1


def apply_usage_governance_headers(response: Response, decision: UsageGovernanceDecision) -> None:
    response.headers["X-Usage-Month"] = decision.month
    response.headers["X-Usage-Requests-Limit"] = str(decision.request_limit)
    response.headers["X-Usage-Requests-Remaining"] = str(max(decision.request_remaining, 0))
    response.headers["X-Usage-Units-Limit"] = str(decision.unit_limit)
    response.headers["X-Usage-Units-Remaining"] = str(max(decision.unit_remaining, 0))


def is_usage_quota_exception(exc: HTTPException) -> bool:
    if exc.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
        return False

    detail = exc.detail
    if not isinstance(detail, dict):
        return False

    error = detail.get("error")
    if not isinstance(error, dict):
        return False

    return error.get("code") == "usage_quota_exceeded"


async def enforce_usage_governance(
    request: Request,
    auth_context: AuthContext,
    estimated_units: int | None = None,
) -> UsageGovernanceDecision:
    month = _month_now()
    units = max(1, int(estimated_units or estimate_request_units(request.method, request.url.path)))

    usage = await get_metering_store().get_usage_for_key(auth_context.key_id, month)
    current_requests = int(usage.get("requests", 0) or 0)
    current_units = int(usage.get("units", 0) or 0)

    request_limit = int(
        auth_context.monthly_request_quota
        if auth_context.monthly_request_quota is not None
        else DEFAULT_MONTHLY_REQUEST_QUOTA
    )
    unit_limit = int(
        auth_context.monthly_unit_quota
        if auth_context.monthly_unit_quota is not None
        else DEFAULT_MONTHLY_UNIT_QUOTA
    )

    would_exceed_requests = current_requests + 1 > request_limit
    would_exceed_units = current_units + units > unit_limit

    if would_exceed_requests or would_exceed_units:
        requests_remaining = max(request_limit - current_requests, 0)
        units_remaining = max(unit_limit - current_units, 0)
        headers = {
            "X-Usage-Month": month,
            "X-Usage-Requests-Limit": str(request_limit),
            "X-Usage-Requests-Remaining": str(requests_remaining),
            "X-Usage-Units-Limit": str(unit_limit),
            "X-Usage-Units-Remaining": str(units_remaining),
        }
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_error_payload(
                "usage_quota_exceeded",
                "Usage quota exceeded for this API key",
                details={
                    "month": month,
                    "requests_limit": request_limit,
                    "requests_used": current_requests,
                    "units_limit": unit_limit,
                    "units_used": current_units,
                    "estimated_units": units,
                },
            ),
            headers=headers,
        )

    return UsageGovernanceDecision(
        month=month,
        request_limit=request_limit,
        request_remaining=max(request_limit - (current_requests + 1), 0),
        unit_limit=unit_limit,
        unit_remaining=max(unit_limit - (current_units + units), 0),
        estimated_units=units,
    )
