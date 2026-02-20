import asyncio

from gateway_api.rate_limiter import InMemoryTokenBucketLimiter


def test_rate_limiter_token_bucket_allows_burst_then_429():
    limiter = InMemoryTokenBucketLimiter()

    first = asyncio.run(limiter.check_and_consume("key", rpm_limit=60, burst_limit=2, cost=1))
    second = asyncio.run(limiter.check_and_consume("key", rpm_limit=60, burst_limit=2, cost=1))
    third = asyncio.run(limiter.check_and_consume("key", rpm_limit=60, burst_limit=2, cost=1))

    assert first.allowed is True
    assert second.allowed is True
    assert third.allowed is False
    assert third.retry_after is not None
