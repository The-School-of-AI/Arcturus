from __future__ import annotations

import os
import secrets
from typing import Any, Dict

from core.generator import AppGenerator
from core.gateway_services.exceptions import IntegrationDependencyUnavailable, UpstreamIntegrationError
from shared.state import PROJECT_ROOT


class SparkAdapter:
    async def generate_page(
        self,
        query: str,
        template: str | None,
        oracle_context: dict[str, Any] | None,
    ) -> Dict[str, Any]:
        if not os.getenv("GEMINI_API_KEY", "").strip():
            raise IntegrationDependencyUnavailable(
                "GEMINI_API_KEY is required for Spark page generation"
            )

        prompt = query.strip()
        if template:
            prompt = f"Template: {template}\n\n{prompt}"

        citations: list[str] = []
        if oracle_context:
            citations = list(oracle_context.get("citations", []))
            if citations:
                prompt += "\n\nUse these references where relevant:\n"
                prompt += "\n".join([f"- {url}" for url in citations[:8]])

        try:
            generator = AppGenerator(project_root=PROJECT_ROOT)
            artifact = await generator.generate_frontend(prompt)
        except Exception as exc:  # noqa: BLE001
            raise UpstreamIntegrationError(f"Spark generation failed: {exc}") from exc

        title = str(artifact.get("name") or query[:80] or "Generated Page")
        page_id = f"page_{secrets.token_hex(6)}"

        return {
            "page_id": page_id,
            "query": query,
            "template": template,
            "title": title,
            "summary": f"Generated page for query: {query}",
            "citations": citations,
            "artifact": artifact,
        }


_spark_adapter: SparkAdapter | None = None


def get_spark_adapter() -> SparkAdapter:
    global _spark_adapter
    if _spark_adapter is None:
        _spark_adapter = SparkAdapter()
    return _spark_adapter
