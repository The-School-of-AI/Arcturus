"""
CostCalculator: Interface and implementation for LLM cost computation.
Single Responsibility: compute cost from token counts and model pricing.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass

from ops.cost.pricing import get_model_pricing


@dataclass
class CostResult:
    """Result of cost computation."""

    cost_usd: float
    input_tokens: int
    output_tokens: int

    def to_dict(self) -> dict:
        """Convert to dict for plan_graph / output compatibility."""
        return {
            "cost": self.cost_usd,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
        }


class CostCalculator(ABC):
    """Abstract interface for cost calculation."""

    @abstractmethod
    def compute(
        self,
        input_tokens: int,
        output_tokens: int,
        model_key: str,
        provider: str,
    ) -> CostResult:
        """Compute cost from token counts and model."""
        pass


class ConfigurableCostCalculator(CostCalculator):
    """
    Cost calculator that reads pricing from config.
    Uses watchtower.cost_pricing in settings.json.
    """

    def compute(
        self,
        input_tokens: int,
        output_tokens: int,
        model_key: str,
        provider: str,
    ) -> CostResult:
        pricing = get_model_pricing(model_key, provider)
        input_cost = (input_tokens / 1000.0) * pricing.input_per_1k
        output_cost = (output_tokens / 1000.0) * pricing.output_per_1k
        total_cost = input_cost + output_cost
        return CostResult(
            cost_usd=round(total_cost, 6),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
