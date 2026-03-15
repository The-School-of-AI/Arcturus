"""Unit tests for ops.cost.CostCalculator."""
import pytest
from unittest.mock import patch

from ops.cost import ConfigurableCostCalculator, CostResult


class TestConfigurableCostCalculator:
    """Tests for ConfigurableCostCalculator behavior."""

    def test_compute_returns_cost_result_with_correct_structure(self):
        """CostResult has cost_usd, input_tokens, output_tokens."""
        with patch("ops.cost.calculator.get_model_pricing") as mock_pricing:
            mock_pricing.return_value = type("P", (), {"input_per_1k": 0.0001, "output_per_1k": 0.0004})()
            calc = ConfigurableCostCalculator()
            result = calc.compute(1000, 500, "gemini-2.5-flash", "gemini")
        assert isinstance(result, CostResult)
        assert hasattr(result, "cost_usd")
        assert hasattr(result, "input_tokens")
        assert hasattr(result, "output_tokens")
        assert result.input_tokens == 1000
        assert result.output_tokens == 500

    def test_compute_calculates_cost_from_pricing(self):
        """Cost is (input/1000)*input_per_1k + (output/1000)*output_per_1k."""
        with patch("ops.cost.calculator.get_model_pricing") as mock_pricing:
            mock_pricing.return_value = type("P", (), {"input_per_1k": 0.001, "output_per_1k": 0.002})()
            calc = ConfigurableCostCalculator()
            result = calc.compute(1000, 500, "test-model", "gemini")
        # 1000/1000 * 0.001 + 500/1000 * 0.002 = 0.001 + 0.001 = 0.002
        assert result.cost_usd == pytest.approx(0.002, rel=1e-5)

    def test_to_dict_includes_cost_input_output_total_tokens(self):
        """CostResult.to_dict() returns dict compatible with plan_graph."""
        with patch("ops.cost.calculator.get_model_pricing") as mock_pricing:
            mock_pricing.return_value = type("P", (), {"input_per_1k": 0.0, "output_per_1k": 0.0})()
            calc = ConfigurableCostCalculator()
            result = calc.compute(100, 50, "ollama", "ollama")
        d = result.to_dict()
        assert d["cost"] == 0.0
        assert d["input_tokens"] == 100
        assert d["output_tokens"] == 50
        assert d["total_tokens"] == 150
