from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass

from fastapi import HTTPException, Response, status

from gateway_api.auth import AuthContext


@dataclass
class _BucketState:
    tokens: float
    last_refill: float


@dataclass
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    reset_seconds: int
    retry_after: int | None = None


class InMemoryTokenBucketLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, _BucketState] = {}
        self._lock = asyncio.Lock()

    async def check_and_consume(
        self,
        key_id: str,
        rpm_limit: int,
        burst_limit: int,
        cost: int = 1,
    ) -> RateLimitDecision:
        now = time.monotonic()

        async with self._lock:
            state = self._buckets.get(key_id)
            if state is None:
                state = _BucketState(tokens=float(burst_limit), last_refill=now)
                self._buckets[key_id] = state

            refill_rate = max(float(rpm_limit), 1.0) / 60.0
            elapsed = max(0.0, now - state.last_refill)
            state.tokens = min(float(burst_limit), state.tokens + (elapsed * refill_rate))
            state.last_refill = now

            if state.tokens >= float(cost):
                state.tokens -= float(cost)
                remaining = max(0, int(math.floor(state.tokens)))
                reset_seconds = int(
                    math.ceil((float(burst_limit) - state.tokens) / refill_rate)
                )
                return RateLimitDecision(
                    allowed=True,
                    limit=rpm_limit,
                    remaining=remaining,
                    reset_seconds=max(reset_seconds, 0),
                )

            needed_tokens = float(cost) - state.tokens
            wait_seconds = int(math.ceil(needed_tokens / refill_rate))
            return RateLimitDecision(
                allowed=False,
                limit=rpm_limit,
                remaining=0,
                reset_seconds=max(wait_seconds, 1),
                retry_after=max(wait_seconds, 1),
            )


limiter = InMemoryTokenBucketLimiter()


def apply_rate_limit_headers(response: Response, decision: RateLimitDecision) -> None:
    response.headers["X-RateLimit-Limit"] = str(decision.limit)
    response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
    response.headers["X-RateLimit-Reset"] = str(decision.reset_seconds)


async def enforce_rate_limit(auth_context: AuthContext, cost: int = 1) -> RateLimitDecision:
    decision = await limiter.check_and_consume(
        key_id=auth_context.key_id,
        rpm_limit=auth_context.rpm_limit,
        burst_limit=auth_context.burst_limit,
        cost=cost,
    )

    if not decision.allowed:
        headers = {
            "Retry-After": str(decision.retry_after or decision.reset_seconds),
            "X-RateLimit-Limit": str(decision.limit),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(decision.reset_seconds),
        }
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "rate_limited",
                    "message": "Rate limit exceeded",
                    "details": {"retry_after_seconds": decision.retry_after},
                }
            },
            headers=headers,
        )

    return decision
