from __future__ import annotations

from typing import Any, Dict

from core.gateway_services.search_service import web_search
from core.gateway_services.exceptions import UpstreamIntegrationError


class OracleAdapter:
    async def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        try:
            result = await web_search(query=query, limit=limit)
        except Exception as exc:  # noqa: BLE001
            raise UpstreamIntegrationError(f"Oracle search failed: {exc}") from exc

        items = result.get("results", [])
        citations = [item.get("url", "") for item in items if item.get("url")]

        return {
            "status": result.get("status", "success"),
            "query": query,
            "results": items,
            "citations": citations,
            "summary": result.get("summary", ""),
        }


_oracle_adapter: OracleAdapter | None = None


def get_oracle_adapter() -> OracleAdapter:
    global _oracle_adapter
    if _oracle_adapter is None:
        _oracle_adapter = OracleAdapter()
    return _oracle_adapter
