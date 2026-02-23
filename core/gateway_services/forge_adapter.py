from __future__ import annotations

import os
from typing import Any, Literal

from core.gateway_services.exceptions import IntegrationDependencyUnavailable, UpstreamIntegrationError
from core.schemas.studio_schema import ArtifactType
from core.studio.orchestrator import ForgeOrchestrator
from shared.state import get_studio_storage


_ARTIFACT_TYPE_MAP = {
    "slides": ArtifactType.slides,
    "document": ArtifactType.document,
    "sheet": ArtifactType.sheet,
}


class ForgeAdapter:
    async def generate_outline(
        self,
        prompt: str,
        artifact_type: Literal["slides", "document", "sheet"],
        template: str | None,
        oracle_context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not os.getenv("GEMINI_API_KEY", "").strip():
            raise IntegrationDependencyUnavailable(
                "GEMINI_API_KEY is required for Forge generation"
            )

        enum_type = _ARTIFACT_TYPE_MAP[artifact_type]

        citations: list[str] = []
        enriched_prompt = prompt.strip()
        if oracle_context:
            citations = list(oracle_context.get("citations", []))
            if citations:
                enriched_prompt += "\n\nIncorporate these references when relevant:\n"
                enriched_prompt += "\n".join([f"- {url}" for url in citations[:8]])

        parameters: dict[str, Any] = {}
        if template:
            parameters["template"] = template

        try:
            orchestrator = ForgeOrchestrator(get_studio_storage())
            result = await orchestrator.generate_outline(
                prompt=enriched_prompt,
                artifact_type=enum_type,
                parameters=parameters,
            )
        except Exception as exc:  # noqa: BLE001
            raise UpstreamIntegrationError(f"Forge outline generation failed: {exc}") from exc

        return {
            "artifact_id": result.get("artifact_id", ""),
            "artifact_type": artifact_type,
            "title": result.get("outline", {}).get("title", ""),
            "status": result.get("status", "pending"),
            "outline": result.get("outline", {}),
            "citations": citations,
        }


_forge_adapter: ForgeAdapter | None = None


def get_forge_adapter() -> ForgeAdapter:
    global _forge_adapter
    if _forge_adapter is None:
        _forge_adapter = ForgeAdapter()
    return _forge_adapter
