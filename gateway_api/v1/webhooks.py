from __future__ import annotations

import time
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response

from gateway_api.auth import AuthContext, require_scope
from gateway_api.contracts import (
    GatewayWebhookDeliveryOut,
    GatewayWebhookDispatchRequest,
    GatewayWebhookDispatchResponse,
    GatewayWebhookInboundRequest,
    GatewayWebhookInboundResponse,
    GatewayWebhookReplayResponse,
    GatewayWebhookSubscriptionCreateRequest,
    GatewayWebhookSubscriptionOut,
    GatewayWebhookTriggerRequest,
    GatewayWebhookTriggerResponse,
)
from gateway_api.integration_tracing import record_integration_event
from gateway_api.metering import record_request
from gateway_api.rate_limiter import apply_rate_limit_headers, enforce_rate_limit
from gateway_api.webhooks import (
    InvalidWebhookSignature,
    StaleWebhookTimestamp,
    WebhookDeliveryError,
    WebhookSigningNotConfigured,
    get_webhook_service,
)

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


def _to_delivery_public(delivery: dict) -> GatewayWebhookDeliveryOut:
    return GatewayWebhookDeliveryOut(
        delivery_id=delivery.get("delivery_id", ""),
        subscription_id=delivery.get("subscription_id", ""),
        target_url=delivery.get("target_url", ""),
        event_type=delivery.get("event_type", ""),
        status=delivery.get("status", "queued"),
        attempt=int(delivery.get("attempt", 0)),
        timestamp=delivery.get("timestamp", ""),
        updated_at=delivery.get("updated_at", delivery.get("timestamp", "")),
        last_error=delivery.get("last_error"),
        next_attempt_at=delivery.get("next_attempt_at"),
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


@router.post("/trigger", response_model=GatewayWebhookTriggerResponse)
async def trigger_webhook_event(
    request: Request,
    payload: GatewayWebhookTriggerRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("webhooks:write")),
) -> GatewayWebhookTriggerResponse:
    start = time.perf_counter()
    status_code = 200
    try:
        decision = await enforce_rate_limit(auth_context)
        apply_rate_limit_headers(response, decision)
        result = await get_webhook_service().trigger_event(
            payload.event_type,
            payload.payload,
            source="api_trigger",
        )
        return GatewayWebhookTriggerResponse(queued_deliveries=result["queued_deliveries"])
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    finally:
        await record_request(request, auth_context.key_id, status_code, start)


@router.post(
    "/inbound/{source}",
    response_model=GatewayWebhookInboundResponse,
    responses={
        401: {"description": "invalid signature"},
        503: {"description": "signing not configured"},
    },
)
async def inbound_webhook(
    source: str,
    request: Request,
    payload: GatewayWebhookInboundRequest,
    x_gateway_signature: Optional[str] = Header(default=None, alias="x-gateway-signature"),
    x_gateway_timestamp: Optional[str] = Header(default=None, alias="x-gateway-timestamp"),
) -> GatewayWebhookInboundResponse:
    start = time.perf_counter()
    status_code = 200
    trace_id = f"trc_{uuid.uuid4().hex[:14]}"

    try:
        raw_body = (await request.body()).decode("utf-8")
        get_webhook_service().validate_inbound_signature(
            signature_header=x_gateway_signature,
            timestamp_header=x_gateway_timestamp,
            raw_body=raw_body,
        )
        await record_integration_event(
            trace_id=trace_id,
            flow="webhook_inbound_validation",
            stage="validate",
            status="success",
            context={"source": source, "event_type": payload.event_type},
        )

        queued = await get_webhook_service().trigger_event(
            event_type=payload.event_type,
            payload=payload.payload,
            source=f"inbound:{source}",
            trace_id=trace_id,
        )
        return GatewayWebhookInboundResponse(
            source=source,
            trace_id=trace_id,
            queued_deliveries=queued["queued_deliveries"],
        )
    except WebhookSigningNotConfigured as exc:
        status_code = 503
        await record_integration_event(
            trace_id=trace_id,
            flow="webhook_inbound_validation",
            stage="validate",
            status="failed",
            context={"reason": str(exc)},
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "webhook_signing_not_configured",
                    "message": str(exc),
                }
            },
        ) from exc
    except (InvalidWebhookSignature, StaleWebhookTimestamp) as exc:
        status_code = 401
        await record_integration_event(
            trace_id=trace_id,
            flow="webhook_inbound_validation",
            stage="validate",
            status="failed",
            context={"reason": str(exc)},
        )
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "invalid_webhook_signature", "message": str(exc)}},
        ) from exc
    except Exception as exc:  # noqa: BLE001
        status_code = 500
        await record_integration_event(
            trace_id=trace_id,
            flow="webhook_inbound_validation",
            stage="validate",
            status="failed",
            context={"reason": str(exc)},
        )
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "webhook_inbound_failed", "message": str(exc)}},
        ) from exc
    finally:
        await record_request(request, "webhook_inbound", status_code, start)


@router.post("/dispatch", response_model=GatewayWebhookDispatchResponse)
async def dispatch_webhook_deliveries(
    request: Request,
    payload: GatewayWebhookDispatchRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("webhooks:write")),
) -> GatewayWebhookDispatchResponse:
    start = time.perf_counter()
    status_code = 200
    trace_id = f"trc_{uuid.uuid4().hex[:14]}"

    try:
        decision = await enforce_rate_limit(auth_context)
        apply_rate_limit_headers(response, decision)

        result = await get_webhook_service().dispatch_pending(
            limit=payload.limit,
            max_attempts=payload.max_attempts,
            base_backoff_seconds=payload.base_backoff_seconds,
        )

        await record_integration_event(
            trace_id=trace_id,
            flow="webhook_delivery_dispatch",
            stage="dispatch",
            status="success",
            context=result,
        )

        return GatewayWebhookDispatchResponse(
            trace_id=trace_id,
            scanned=result["scanned"],
            delivered=result["delivered"],
            retried=result["retried"],
            dead_lettered=result["dead_lettered"],
        )
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    except Exception as exc:  # noqa: BLE001
        status_code = 500
        await record_integration_event(
            trace_id=trace_id,
            flow="webhook_delivery_dispatch",
            stage="dispatch",
            status="failed",
            context={"reason": str(exc)},
        )
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "webhook_dispatch_failed", "message": str(exc)}},
        ) from exc
    finally:
        await record_request(request, auth_context.key_id, status_code, start)


@router.get("/deliveries", response_model=List[GatewayWebhookDeliveryOut])
async def list_webhook_deliveries(
    request: Request,
    response: Response,
    status: Optional[str] = None,
    limit: int = 100,
    auth_context: AuthContext = Depends(require_scope("webhooks:read")),
) -> List[GatewayWebhookDeliveryOut]:
    start = time.perf_counter()
    status_code = 200
    try:
        decision = await enforce_rate_limit(auth_context)
        apply_rate_limit_headers(response, decision)

        rows = await get_webhook_service().list_deliveries(status=status, limit=limit)
        return [_to_delivery_public(item) for item in rows]
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    finally:
        await record_request(request, auth_context.key_id, status_code, start)


@router.post("/dlq/{delivery_id}/replay", response_model=GatewayWebhookReplayResponse)
async def replay_dead_letter(
    delivery_id: str,
    request: Request,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("webhooks:write")),
) -> GatewayWebhookReplayResponse:
    start = time.perf_counter()
    status_code = 200
    trace_id = f"trc_{uuid.uuid4().hex[:14]}"
    try:
        decision = await enforce_rate_limit(auth_context)
        apply_rate_limit_headers(response, decision)

        await get_webhook_service().replay_dead_letter(delivery_id)
        await record_integration_event(
            trace_id=trace_id,
            flow="webhook_delivery_dispatch",
            stage="dlq_replay",
            status="success",
            context={"delivery_id": delivery_id},
        )

        return GatewayWebhookReplayResponse(trace_id=trace_id, delivery_id=delivery_id)
    except WebhookDeliveryError as exc:
        status_code = 404
        await record_integration_event(
            trace_id=trace_id,
            flow="webhook_delivery_dispatch",
            stage="dlq_replay",
            status="failed",
            context={"reason": str(exc)},
        )
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "webhook_delivery_not_found", "message": str(exc)}},
        ) from exc
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    finally:
        await record_request(request, auth_context.key_id, status_code, start)
