from __future__ import annotations

import time
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from gateway_api.auth import AuthContext, require_scope
from gateway_api.contracts import (
    GatewayWebhookSubscriptionCreateRequest,
    GatewayWebhookSubscriptionOut,
    GatewayWebhookTriggerRequest,
)
from gateway_api.metering import record_request
from gateway_api.rate_limiter import apply_rate_limit_headers, enforce_rate_limit
from gateway_api.webhooks import get_webhook_service

router = APIRouter(prefix="/webhooks", tags=["Gateway V1"])


def _to_public(subscription: dict) -> GatewayWebhookSubscriptionOut:
    return GatewayWebhookSubscriptionOut(
        id=subscription["id"],
        target_url=subscription["target_url"],
        event_types=subscription.get("event_types", []),
        active=subscription.get("active", True),
        secret_prefix=(subscription.get("secret", "")[:8] + "...")
        if subscription.get("secret")
        else "",
        created_at=subscription.get("created_at", ""),
    )


@router.get("", response_model=List[GatewayWebhookSubscriptionOut])
async def list_subscriptions(
    request: Request,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("webhooks:write")),
) -> List[GatewayWebhookSubscriptionOut]:
    start = time.perf_counter()
    status_code = 200
    try:
        decision = await enforce_rate_limit(auth_context)
        apply_rate_limit_headers(response, decision)

        subscriptions = await get_webhook_service().list_subscriptions()
        return [_to_public(item) for item in subscriptions]
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    finally:
        await record_request(request, auth_context.key_id, status_code, start)


@router.post("", response_model=GatewayWebhookSubscriptionOut)
async def create_subscription(
    request: Request,
    payload: GatewayWebhookSubscriptionCreateRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("webhooks:write")),
) -> GatewayWebhookSubscriptionOut:
    start = time.perf_counter()
    status_code = 200
    try:
        decision = await enforce_rate_limit(auth_context)
        apply_rate_limit_headers(response, decision)

        if not payload.event_types:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "invalid_event_types",
                        "message": "event_types must contain at least one event",
                    }
                },
            )

        subscription = await get_webhook_service().create_subscription(
            payload.target_url,
            payload.event_types,
            payload.secret,
            payload.active,
        )
        return _to_public(subscription)
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    finally:
        await record_request(request, auth_context.key_id, status_code, start)


@router.delete("/{subscription_id}", response_model=dict)
async def delete_subscription(
    subscription_id: str,
    request: Request,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("webhooks:write")),
) -> dict:
    start = time.perf_counter()
    status_code = 200
    try:
        decision = await enforce_rate_limit(auth_context)
        apply_rate_limit_headers(response, decision)

        deleted = await get_webhook_service().delete_subscription(subscription_id)
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": "subscription_not_found",
                        "message": "Webhook subscription not found",
                    }
                },
            )
        return {"status": "deleted", "id": subscription_id}
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    finally:
        await record_request(request, auth_context.key_id, status_code, start)


@router.post("/trigger", response_model=dict)
async def trigger_webhook_event(
    request: Request,
    payload: GatewayWebhookTriggerRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("webhooks:write")),
) -> dict:
    start = time.perf_counter()
    status_code = 200
    try:
        decision = await enforce_rate_limit(auth_context)
        apply_rate_limit_headers(response, decision)
        return await get_webhook_service().trigger_event(payload.event_type, payload.payload)
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    finally:
        await record_request(request, auth_context.key_id, status_code, start)
