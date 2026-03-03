from __future__ import annotations

import time
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder

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
from gateway_api.idempotency import (
    begin_idempotent_request,
    derive_inbound_idempotency_key,
    finalize_idempotent_failure,
    finalize_idempotent_success,
)
from gateway_api.integration_tracing import record_integration_event
from gateway_api.metering import record_request
from gateway_api.rate_limiter import enforce_rate_limit_and_usage_governance
from gateway_api.usage_governance import is_usage_quota_exception
from gateway_api.webhooks import (
    InvalidWebhookSignature,
    StaleWebhookTimestamp,
    WebhookDeliveryError,
    WebhookSigningNotConfigured,
    get_webhook_service,
)

router = APIRouter(prefix="/webhooks", tags=["Gateway V1"])
IDEMPOTENCY_HEADER = "Idempotency-Key"


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
    usage_units = 1
    governance_denied = False
    try:
        _, usage_decision = await enforce_rate_limit_and_usage_governance(
            request=request,
            response=response,
            auth_context=auth_context,
        )
        usage_units = usage_decision.estimated_units

        subscriptions = await get_webhook_service().list_subscriptions()
        return [_to_public(item) for item in subscriptions]
    except HTTPException as exc:
        status_code = exc.status_code
        if is_usage_quota_exception(exc):
            governance_denied = True
        raise
    finally:
        await record_request(
            request,
            auth_context.key_id,
            status_code,
            start,
            units=usage_units,
            governance_denied=governance_denied,
            billable=not governance_denied,
        )


@router.post("", response_model=GatewayWebhookSubscriptionOut)
async def create_subscription(
    request: Request,
    payload: GatewayWebhookSubscriptionCreateRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("webhooks:write")),
    idempotency_key: Optional[str] = Header(default=None, alias=IDEMPOTENCY_HEADER),
) -> GatewayWebhookSubscriptionOut:
    start = time.perf_counter()
    status_code = 200
    usage_units = 2
    governance_denied = False
    billable_request = True
    idempotency_context = None
    try:
        idempotency_context, replay = await begin_idempotent_request(
            request=request,
            actor=auth_context.key_id,
            idempotency_key=idempotency_key,
            payload=payload.model_dump(mode="json"),
            response=response,
        )
        if replay is not None:
            billable_request = False
            status_code = replay.status_code
            return replay

        _, usage_decision = await enforce_rate_limit_and_usage_governance(
            request=request,
            response=response,
            auth_context=auth_context,
            estimated_units=2,
        )
        usage_units = usage_decision.estimated_units

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
        result = _to_public(subscription)

        if idempotency_context is not None:
            await finalize_idempotent_success(
                idempotency_context,
                status_code=200,
                response_body=jsonable_encoder(result),
                response_headers={
                    "X-Idempotency-Status": "created",
                    "X-Idempotency-Key": idempotency_context.idempotency_key,
                },
            )
        return result
    except HTTPException as exc:
        status_code = exc.status_code
        if idempotency_context is not None:
            await finalize_idempotent_failure(
                idempotency_context,
                status_code=exc.status_code,
                detail=exc.detail,
            )
        if is_usage_quota_exception(exc):
            governance_denied = True
        raise
    finally:
        await record_request(
            request,
            auth_context.key_id,
            status_code,
            start,
            units=usage_units,
            governance_denied=governance_denied,
            billable=billable_request and not governance_denied,
        )


@router.delete("/{subscription_id}", response_model=dict)
async def delete_subscription(
    subscription_id: str,
    request: Request,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("webhooks:write")),
    idempotency_key: Optional[str] = Header(default=None, alias=IDEMPOTENCY_HEADER),
) -> dict:
    start = time.perf_counter()
    status_code = 200
    usage_units = 2
    governance_denied = False
    billable_request = True
    idempotency_context = None
    try:
        idempotency_context, replay = await begin_idempotent_request(
            request=request,
            actor=auth_context.key_id,
            idempotency_key=idempotency_key,
            payload={"subscription_id": subscription_id},
            response=response,
        )
        if replay is not None:
            billable_request = False
            status_code = replay.status_code
            return replay

        _, usage_decision = await enforce_rate_limit_and_usage_governance(
            request=request,
            response=response,
            auth_context=auth_context,
            estimated_units=2,
        )
        usage_units = usage_decision.estimated_units

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

        result = {"status": "deleted", "id": subscription_id}
        if idempotency_context is not None:
            await finalize_idempotent_success(
                idempotency_context,
                status_code=200,
                response_body=result,
                response_headers={
                    "X-Idempotency-Status": "created",
                    "X-Idempotency-Key": idempotency_context.idempotency_key,
                },
            )

        return result
    except HTTPException as exc:
        status_code = exc.status_code
        if idempotency_context is not None:
            await finalize_idempotent_failure(
                idempotency_context,
                status_code=exc.status_code,
                detail=exc.detail,
            )
        if is_usage_quota_exception(exc):
            governance_denied = True
        raise
    finally:
        await record_request(
            request,
            auth_context.key_id,
            status_code,
            start,
            units=usage_units,
            governance_denied=governance_denied,
            billable=billable_request and not governance_denied,
        )


@router.post("/trigger", response_model=GatewayWebhookTriggerResponse)
async def trigger_webhook_event(
    request: Request,
    payload: GatewayWebhookTriggerRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("webhooks:write")),
    idempotency_key: Optional[str] = Header(default=None, alias=IDEMPOTENCY_HEADER),
) -> GatewayWebhookTriggerResponse:
    start = time.perf_counter()
    status_code = 200
    usage_units = 2
    governance_denied = False
    billable_request = True
    idempotency_context = None
    try:
        idempotency_context, replay = await begin_idempotent_request(
            request=request,
            actor=auth_context.key_id,
            idempotency_key=idempotency_key,
            payload=payload.model_dump(mode="json"),
            response=response,
        )
        if replay is not None:
            billable_request = False
            status_code = replay.status_code
            return replay

        _, usage_decision = await enforce_rate_limit_and_usage_governance(
            request=request,
            response=response,
            auth_context=auth_context,
            estimated_units=2,
        )
        usage_units = usage_decision.estimated_units

        result = await get_webhook_service().trigger_event(
            payload.event_type,
            payload.payload,
            source="api_trigger",
        )
        response_payload = GatewayWebhookTriggerResponse(
            queued_deliveries=result["queued_deliveries"]
        )

        if idempotency_context is not None:
            await finalize_idempotent_success(
                idempotency_context,
                status_code=200,
                response_body=jsonable_encoder(response_payload),
                response_headers={
                    "X-Idempotency-Status": "created",
                    "X-Idempotency-Key": idempotency_context.idempotency_key,
                },
            )
        return response_payload
    except HTTPException as exc:
        status_code = exc.status_code
        if idempotency_context is not None:
            await finalize_idempotent_failure(
                idempotency_context,
                status_code=exc.status_code,
                detail=exc.detail,
            )
        if is_usage_quota_exception(exc):
            governance_denied = True
        raise
    finally:
        await record_request(
            request,
            auth_context.key_id,
            status_code,
            start,
            units=usage_units,
            governance_denied=governance_denied,
            billable=billable_request and not governance_denied,
        )


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
    response: Response,
    payload: GatewayWebhookInboundRequest,
    x_gateway_signature: Optional[str] = Header(default=None, alias="x-gateway-signature"),
    x_gateway_timestamp: Optional[str] = Header(default=None, alias="x-gateway-timestamp"),
) -> GatewayWebhookInboundResponse:
    start = time.perf_counter()
    status_code = 200
    trace_id = f"trc_{uuid.uuid4().hex[:14]}"
    billable_request = True
    idempotency_context = None

    raw_body = (await request.body()).decode("utf-8")
    derived_key = derive_inbound_idempotency_key(
        source=source,
        signature_header=x_gateway_signature,
        timestamp_header=x_gateway_timestamp,
        raw_body=raw_body,
    )

    try:
        idempotency_context, replay = await begin_idempotent_request(
            request=request,
            actor="webhook_inbound",
            idempotency_key=derived_key,
            payload=payload.model_dump(mode="json"),
            response=response,
        )
        if replay is not None:
            billable_request = False
            status_code = replay.status_code
            return replay

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
        response_payload = GatewayWebhookInboundResponse(
            source=source,
            trace_id=trace_id,
            queued_deliveries=queued["queued_deliveries"],
        )

        if idempotency_context is not None:
            await finalize_idempotent_success(
                idempotency_context,
                status_code=200,
                response_body=jsonable_encoder(response_payload),
                response_headers={
                    "X-Idempotency-Status": "created",
                    "X-Idempotency-Key": derived_key,
                },
            )

        return response_payload
    except WebhookSigningNotConfigured as exc:
        status_code = 503
        await record_integration_event(
            trace_id=trace_id,
            flow="webhook_inbound_validation",
            stage="validate",
            status="failed",
            context={"reason": str(exc)},
        )
        detail = {
            "error": {
                "code": "webhook_signing_not_configured",
                "message": str(exc),
            }
        }
        if idempotency_context is not None:
            await finalize_idempotent_failure(
                idempotency_context,
                status_code=503,
                detail=detail,
            )
        raise HTTPException(status_code=503, detail=detail) from exc
    except (InvalidWebhookSignature, StaleWebhookTimestamp) as exc:
        status_code = 401
        await record_integration_event(
            trace_id=trace_id,
            flow="webhook_inbound_validation",
            stage="validate",
            status="failed",
            context={"reason": str(exc)},
        )
        detail = {"error": {"code": "invalid_webhook_signature", "message": str(exc)}}
        if idempotency_context is not None:
            await finalize_idempotent_failure(
                idempotency_context,
                status_code=401,
                detail=detail,
            )
        raise HTTPException(status_code=401, detail=detail) from exc
    except HTTPException as exc:
        status_code = exc.status_code
        if idempotency_context is not None:
            await finalize_idempotent_failure(
                idempotency_context,
                status_code=exc.status_code,
                detail=exc.detail,
            )
        raise
    except Exception as exc:  # noqa: BLE001
        status_code = 500
        await record_integration_event(
            trace_id=trace_id,
            flow="webhook_inbound_validation",
            stage="validate",
            status="failed",
            context={"reason": str(exc)},
        )
        detail = {"error": {"code": "webhook_inbound_failed", "message": str(exc)}}
        if idempotency_context is not None:
            await finalize_idempotent_failure(
                idempotency_context,
                status_code=500,
                detail=detail,
            )
        raise HTTPException(status_code=500, detail=detail) from exc
    finally:
        await record_request(
            request,
            "webhook_inbound",
            status_code,
            start,
            units=2,
            billable=billable_request,
        )


@router.post("/dispatch", response_model=GatewayWebhookDispatchResponse)
async def dispatch_webhook_deliveries(
    request: Request,
    payload: GatewayWebhookDispatchRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("webhooks:write")),
    idempotency_key: Optional[str] = Header(default=None, alias=IDEMPOTENCY_HEADER),
) -> GatewayWebhookDispatchResponse:
    start = time.perf_counter()
    status_code = 200
    trace_id = f"trc_{uuid.uuid4().hex[:14]}"
    usage_units = 2
    governance_denied = False
    billable_request = True
    idempotency_context = None

    try:
        idempotency_context, replay = await begin_idempotent_request(
            request=request,
            actor=auth_context.key_id,
            idempotency_key=idempotency_key,
            payload=payload.model_dump(mode="json"),
            response=response,
        )
        if replay is not None:
            billable_request = False
            status_code = replay.status_code
            return replay

        _, usage_decision = await enforce_rate_limit_and_usage_governance(
            request=request,
            response=response,
            auth_context=auth_context,
            estimated_units=2,
        )
        usage_units = usage_decision.estimated_units

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

        response_payload = GatewayWebhookDispatchResponse(
            trace_id=trace_id,
            scanned=result["scanned"],
            delivered=result["delivered"],
            retried=result["retried"],
            dead_lettered=result["dead_lettered"],
        )

        if idempotency_context is not None:
            await finalize_idempotent_success(
                idempotency_context,
                status_code=200,
                response_body=jsonable_encoder(response_payload),
                response_headers={
                    "X-Idempotency-Status": "created",
                    "X-Idempotency-Key": idempotency_context.idempotency_key,
                },
            )

        return response_payload
    except HTTPException as exc:
        status_code = exc.status_code
        if idempotency_context is not None:
            await finalize_idempotent_failure(
                idempotency_context,
                status_code=exc.status_code,
                detail=exc.detail,
            )
        if is_usage_quota_exception(exc):
            governance_denied = True
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
        detail = {"error": {"code": "webhook_dispatch_failed", "message": str(exc)}}
        if idempotency_context is not None:
            await finalize_idempotent_failure(
                idempotency_context,
                status_code=500,
                detail=detail,
            )
        raise HTTPException(status_code=500, detail=detail) from exc
    finally:
        await record_request(
            request,
            auth_context.key_id,
            status_code,
            start,
            units=usage_units,
            governance_denied=governance_denied,
            billable=billable_request and not governance_denied,
        )


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
    usage_units = 1
    governance_denied = False
    try:
        _, usage_decision = await enforce_rate_limit_and_usage_governance(
            request=request,
            response=response,
            auth_context=auth_context,
        )
        usage_units = usage_decision.estimated_units

        rows = await get_webhook_service().list_deliveries(status=status, limit=limit)
        return [_to_delivery_public(item) for item in rows]
    except HTTPException as exc:
        status_code = exc.status_code
        if is_usage_quota_exception(exc):
            governance_denied = True
        raise
    finally:
        await record_request(
            request,
            auth_context.key_id,
            status_code,
            start,
            units=usage_units,
            governance_denied=governance_denied,
            billable=not governance_denied,
        )


@router.post("/dlq/{delivery_id}/replay", response_model=GatewayWebhookReplayResponse)
async def replay_dead_letter(
    delivery_id: str,
    request: Request,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("webhooks:write")),
    idempotency_key: Optional[str] = Header(default=None, alias=IDEMPOTENCY_HEADER),
) -> GatewayWebhookReplayResponse:
    start = time.perf_counter()
    status_code = 200
    trace_id = f"trc_{uuid.uuid4().hex[:14]}"
    usage_units = 2
    governance_denied = False
    billable_request = True
    idempotency_context = None
    try:
        idempotency_context, replay = await begin_idempotent_request(
            request=request,
            actor=auth_context.key_id,
            idempotency_key=idempotency_key,
            payload={"delivery_id": delivery_id},
            response=response,
        )
        if replay is not None:
            billable_request = False
            status_code = replay.status_code
            return replay

        _, usage_decision = await enforce_rate_limit_and_usage_governance(
            request=request,
            response=response,
            auth_context=auth_context,
            estimated_units=2,
        )
        usage_units = usage_decision.estimated_units

        await get_webhook_service().replay_dead_letter(delivery_id)
        await record_integration_event(
            trace_id=trace_id,
            flow="webhook_delivery_dispatch",
            stage="dlq_replay",
            status="success",
            context={"delivery_id": delivery_id},
        )

        response_payload = GatewayWebhookReplayResponse(trace_id=trace_id, delivery_id=delivery_id)
        if idempotency_context is not None:
            await finalize_idempotent_success(
                idempotency_context,
                status_code=200,
                response_body=jsonable_encoder(response_payload),
                response_headers={
                    "X-Idempotency-Status": "created",
                    "X-Idempotency-Key": idempotency_context.idempotency_key,
                },
            )

        return response_payload
    except WebhookDeliveryError as exc:
        status_code = 404
        await record_integration_event(
            trace_id=trace_id,
            flow="webhook_delivery_dispatch",
            stage="dlq_replay",
            status="failed",
            context={"reason": str(exc)},
        )
        detail = {"error": {"code": "webhook_delivery_not_found", "message": str(exc)}}
        if idempotency_context is not None:
            await finalize_idempotent_failure(
                idempotency_context,
                status_code=404,
                detail=detail,
            )
        raise HTTPException(status_code=404, detail=detail) from exc
    except HTTPException as exc:
        status_code = exc.status_code
        if idempotency_context is not None:
            await finalize_idempotent_failure(
                idempotency_context,
                status_code=exc.status_code,
                detail=exc.detail,
            )
        if is_usage_quota_exception(exc):
            governance_denied = True
        raise
    finally:
        await record_request(
            request,
            auth_context.key_id,
            status_code,
            start,
            units=usage_units,
            governance_denied=governance_denied,
            billable=billable_request and not governance_denied,
        )
