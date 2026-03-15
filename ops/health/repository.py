"""
Health check repository: MongoDB persistence for service health snapshots.

Stores periodic health check results in watchtower.health_checks collection.
Supports querying history by time window and service, and computing uptime
percentages for SLA monitoring.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ops.health.models import HealthResult, ResourceSnapshot

Collection = Any


def _since_datetime(hours: int) -> datetime:
    """Time cutoff for time-range queries."""
    return datetime.utcnow() - timedelta(hours=hours)


class HealthRepository:
    """MongoDB persistence for health check snapshots."""

    _indexes_ensured: bool = False

    def __init__(self, collection: Collection):
        self._coll = collection
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        if HealthRepository._indexes_ensured:
            return
        try:
            self._coll.create_index([("timestamp", -1)])
            self._coll.create_index([("service", 1), ("timestamp", -1)])
            HealthRepository._indexes_ensured = True
        except Exception:
            pass

    def save_snapshot(
        self,
        results: List[HealthResult],
        resources: Optional[ResourceSnapshot] = None,
    ) -> int:
        """
        Persist one document per service from a single health check round.

        Returns the number of documents inserted.
        """
        now = datetime.utcnow()
        resource_dict = resources.to_dict() if resources else None

        docs = []
        for result in results:
            doc: Dict[str, Any] = {
                "timestamp": now,
                "service": result.service,
                "status": result.status,
                "latency_ms": result.latency_ms,
                "details": result.details,
            }
            if resource_dict is not None:
                doc["resources"] = resource_dict
            docs.append(doc)

        if not docs:
            return 0
        insert_result = self._coll.insert_many(docs)
        return len(insert_result.inserted_ids)

    def get_history(
        self,
        hours: int = 24,
        service: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """
        Query health snapshots within a time window.

        Args:
            hours: How far back to look.
            service: Optional filter by service name.
            limit: Maximum documents to return.

        Returns:
            List of snapshot dicts with ISO timestamps, sorted newest first.
        """
        since = _since_datetime(hours)
        query: Dict[str, Any] = {"timestamp": {"$gte": since}}
        if service:
            query["service"] = service

        cursor = self._coll.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit)
        snapshots = []
        for doc in cursor:
            if "timestamp" in doc and isinstance(doc["timestamp"], datetime):
                doc["timestamp"] = doc["timestamp"].isoformat()
            snapshots.append(doc)
        return snapshots

    def compute_uptime(
        self,
        service: str,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Compute uptime percentage for a service over a time window.

        Uptime = (ok_checks / total_checks) * 100.
        """
        since = _since_datetime(hours)
        pipeline = [
            {"$match": {"service": service, "timestamp": {"$gte": since}}},
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": 1},
                    "ok_count": {"$sum": {"$cond": [{"$eq": ["$status", "ok"]}, 1, 0]}},
                    "degraded_count": {
                        "$sum": {"$cond": [{"$eq": ["$status", "degraded"]}, 1, 0]}
                    },
                    "down_count": {
                        "$sum": {"$cond": [{"$eq": ["$status", "down"]}, 1, 0]}
                    },
                    "avg_latency_ms": {"$avg": "$latency_ms"},
                }
            },
        ]
        row = next(self._coll.aggregate(pipeline), None)
        if not row or row["total"] == 0:
            return {
                "service": service,
                "hours": hours,
                "uptime_pct": 100.0,
                "total_checks": 0,
                "ok_checks": 0,
                "degraded_checks": 0,
                "down_checks": 0,
                "avg_latency_ms": None,
            }

        total = row["total"]
        ok_count = row["ok_count"]
        uptime_pct = round((ok_count / total) * 100, 2)
        avg_latency = round(row["avg_latency_ms"], 2) if row["avg_latency_ms"] else None

        return {
            "service": service,
            "hours": hours,
            "uptime_pct": uptime_pct,
            "total_checks": total,
            "ok_checks": ok_count,
            "degraded_checks": row["degraded_count"],
            "down_checks": row["down_count"],
            "avg_latency_ms": avg_latency,
        }

    def compute_all_uptimes(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Compute uptime for every service that has snapshots in the window."""
        since = _since_datetime(hours)
        pipeline = [
            {"$match": {"timestamp": {"$gte": since}}},
            {"$group": {"_id": "$service"}},
        ]
        services = [doc["_id"] for doc in self._coll.aggregate(pipeline)]
        return [self.compute_uptime(svc, hours) for svc in sorted(services)]
