"""
Metrics API Router - Provides dashboard analytics endpoints
"""
from fastapi import APIRouter
from core.metrics_aggregator import get_aggregator

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("/dashboard")
async def get_dashboard_metrics():
    """
    Get aggregated dashboard metrics.
    Returns:
    - totals: Overall run statistics
    - by_agent: Per-agent breakdown
    - by_day: Daily usage trend (last 30 days)
    """
    aggregator = get_aggregator()
    return aggregator.get_dashboard_metrics()


@router.post("/refresh")
async def refresh_metrics():
    """
    Force refresh of metrics cache.
    Useful after data changes or to get real-time stats.
    """
    aggregator = get_aggregator()
    return aggregator.get_dashboard_metrics(force_refresh=True)
