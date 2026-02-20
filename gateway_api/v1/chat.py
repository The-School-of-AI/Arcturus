from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from config.settings_loader import settings
from gateway_api.auth import AuthContext, require_scope
from gateway_api.contracts import (
    GatewayChatChoice,
    GatewayChatChoiceMessage,
    GatewayChatCompletionsRequest,
    GatewayChatCompletionsResponse,
    GatewayUsageStats,
)
from gateway_api.metering import record_request
from gateway_api.rate_limiter import apply_rate_limit_headers, enforce_rate_limit
from routers.runs import process_run

router = APIRouter(prefix="/chat", tags=["Gateway V1"])


@router.post("/completions", response_model=GatewayChatCompletionsResponse)
async def chat_completions(
    request: Request,
    payload: GatewayChatCompletionsRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("chat:write")),
) -> GatewayChatCompletionsResponse:
    start = time.perf_counter()
    status_code = 200

    try:
        decision = await enforce_rate_limit(auth_context)
        apply_rate_limit_headers(response, decision)

        if payload.stream:
            raise HTTPException(
                status_code=501,
                detail={
                    "error": {
                        "code": "stream_not_supported",
                        "message": "Streaming is not supported yet",
                    }
                },
            )

        user_messages = [msg.content for msg in payload.messages if msg.role == "user"]
        if not user_messages:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "invalid_messages",
                        "message": "At least one user message is required",
                    }
                },
            )

        query = "\n".join(user_messages)
        run_id = f"gw_chat_{uuid.uuid4().hex[:12]}"
        result = await process_run(run_id, query)

        output = result.get("output") or result.get("summary") or "No output produced."
        selected_model = payload.model or settings.get("agent", {}).get(
            "default_model", "gemini-2.5-flash"
        )

        prompt_tokens = max(1, len(query.split()))
        completion_tokens = max(1, len(output.split()))

        return GatewayChatCompletionsResponse(
            id=f"chatcmpl_{uuid.uuid4().hex[:16]}",
            created=int(time.time()),
            model=selected_model,
            choices=[
                GatewayChatChoice(
                    index=0,
                    message=GatewayChatChoiceMessage(content=output),
                )
            ],
            usage=GatewayUsageStats(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )

    except HTTPException as exc:
        status_code = exc.status_code
        raise
    except Exception as exc:  # noqa: BLE001
        status_code = 500
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "chat_failed", "message": str(exc)}},
        ) from exc
    finally:
        await record_request(request, auth_context.key_id, status_code, start)
