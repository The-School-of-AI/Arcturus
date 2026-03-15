"""
Pricing configuration loader for cost calculation.
Reads per-model $/1K token rates from watchtower.cost_pricing in settings.
"""
from dataclasses import dataclass
from typing import Any

from config.settings_loader import load_settings


@dataclass
class ModelPricing:
    """Pricing for a single model (USD per 1K tokens)."""

    input_per_1k: float
    output_per_1k: float


def get_pricing_config() -> dict[str, Any]:
    """Load cost pricing from watchtower.cost_pricing in settings."""
    settings = load_settings()
    watchtower = settings.get("watchtower", {})
    return watchtower.get("cost_pricing", {})


def get_model_pricing(model_key: str, provider: str) -> ModelPricing:
    """
    Get pricing for a model. Falls back to provider-level then default.
    Returns ModelPricing with input_per_1k and output_per_1k in USD.
    """
    config = get_pricing_config()
    default = config.get("default", {"input_per_1k": 0.0001, "output_per_1k": 0.0004})

    # Try exact model key first (e.g. gemini-2.5-flash)
    model_cfg = config.get(model_key)
    if model_cfg:
        return ModelPricing(
            input_per_1k=float(model_cfg.get("input_per_1k", default["input_per_1k"])),
            output_per_1k=float(model_cfg.get("output_per_1k", default["output_per_1k"])),
        )

    # Try provider-level (e.g. gemini, ollama)
    provider_cfg = config.get(provider)
    if provider_cfg:
        return ModelPricing(
            input_per_1k=float(provider_cfg.get("input_per_1k", default["input_per_1k"])),
            output_per_1k=float(provider_cfg.get("output_per_1k", default["output_per_1k"])),
        )

    return ModelPricing(
        input_per_1k=float(default["input_per_1k"]),
        output_per_1k=float(default["output_per_1k"]),
    )
