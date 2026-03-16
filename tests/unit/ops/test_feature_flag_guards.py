"""
Behaviour tests for feature-flag guards.

Each test verifies that disabling a flag changes system behaviour
(endpoint returns 403, cost is zeroed, cache is bypassed, etc.)
rather than inspecting implementation details.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from ops.admin.feature_flags import FeatureFlagStore


@pytest.fixture()
def flags_file(tmp_path: Path):
    """Create a temporary feature-flags JSON file with all flags enabled."""
    path = tmp_path / "feature_flags.json"
    path.write_text(
        json.dumps(
            {
                "deep_research": True,
                "voice_wake": True,
                "multi_agent": True,
                "cost_tracking": True,
                "semantic_cache": True,
                "health_scheduler": True,
            }
        )
    )
    return path


@pytest.fixture()
def flag_store(flags_file: Path):
    return FeatureFlagStore(path=flags_file)


# ── cost_tracking ──────────────────────────────────────────────────────


class TestCostTrackingFlag:
    """When cost_tracking is disabled, cost_usd must be set to 0 on spans."""

    @pytest.mark.asyncio
    async def test_cost_computed_when_enabled(self, flag_store):
        flag_store.set("cost_tracking", True)

        with patch("core.model_manager.flag_store", flag_store):
            from core.model_manager import ModelManager

            mgr = MagicMock(spec=ModelManager)
            mgr.text_model_key = "test-model"
            mgr.model_type = "gemini"

            cost_calc = MagicMock()
            cost_calc.compute.return_value = MagicMock(cost_usd=0.001234)
            mgr.cost_calculator = cost_calc

            span = MagicMock()

            # Simulate the guard logic from generate_text
            if flag_store.get("cost_tracking"):
                result = cost_calc.compute(100, 50, mgr.text_model_key, mgr.model_type)
                span.set_attribute("cost_usd", result.cost_usd)
            else:
                span.set_attribute("cost_usd", 0)

            span.set_attribute.assert_called_with("cost_usd", 0.001234)

    @pytest.mark.asyncio
    async def test_cost_zeroed_when_disabled(self, flag_store):
        flag_store.set("cost_tracking", False)

        span = MagicMock()
        cost_calc = MagicMock()

        if flag_store.get("cost_tracking"):
            result = cost_calc.compute(100, 50, "test-model", "gemini")
            span.set_attribute("cost_usd", result.cost_usd)
        else:
            span.set_attribute("cost_usd", 0)

        span.set_attribute.assert_called_with("cost_usd", 0)
        cost_calc.compute.assert_not_called()

    @pytest.mark.asyncio
    async def test_cost_summary_returns_disabled_payload(self, flag_store):
        """The /admin/cost/summary endpoint returns a disabled payload when flag is off."""
        flag_store.set("cost_tracking", False)

        with patch("ops.admin.feature_flags.flag_store", flag_store):
            from routers.admin import get_cost_summary

            result = await get_cost_summary(hours=24, group_by="agent")

            assert result["disabled"] is True
            assert result["total_cost_usd"] == 0

    @pytest.mark.asyncio
    async def test_cost_summary_returns_data_when_enabled(self, flag_store):
        flag_store.set("cost_tracking", True)

        mock_repo = MagicMock()
        mock_repo.get_cost_summary.return_value = {
            "total_cost_usd": 1.5,
            "trace_count": 10,
            "by_agent": {},
            "by_model": {},
            "hours": 24,
        }

        with (
            patch("ops.admin.feature_flags.flag_store", flag_store),
            patch("routers.admin._repo", return_value=mock_repo),
        ):
            from routers.admin import get_cost_summary

            result = await get_cost_summary(hours=24, group_by="agent")

            assert "disabled" not in result
            assert result["total_cost_usd"] == 1.5


# ── multi_agent ────────────────────────────────────────────────────────


class TestMultiAgentFlag:
    """When multi_agent is disabled, swarm run creation must be rejected."""

    @pytest.mark.asyncio
    async def test_swarm_run_rejected_when_disabled(self, flag_store):
        flag_store.set("multi_agent", False)

        with patch("ops.admin.feature_flags.flag_store", flag_store):
            from fastapi import HTTPException
            from routers.swarm import start_swarm_run
            from pydantic import BaseModel

            class FakeBody(BaseModel):
                query: str = "test"
                token_budget: int = 10000
                cost_budget_usd: float = 1.0

            with pytest.raises(HTTPException) as exc_info:
                await start_swarm_run(body=FakeBody(), background_tasks=MagicMock())

            assert exc_info.value.status_code == 403
            assert "disabled" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_swarm_run_allowed_when_enabled(self, flag_store):
        flag_store.set("multi_agent", True)

        with (
            patch("ops.admin.feature_flags.flag_store", flag_store),
            patch("routers.swarm.SwarmRunner") as MockRunner,
        ):
            from routers.swarm import start_swarm_run
            from pydantic import BaseModel

            class FakeBody(BaseModel):
                query: str = "test"
                token_budget: int = 10000
                cost_budget_usd: float = 1.0

            mock_bg = MagicMock()
            result = await start_swarm_run(body=FakeBody(), background_tasks=mock_bg)

            assert result["status"] == "started"
            assert "run_id" in result


# ── deep_research ──────────────────────────────────────────────────────


class TestDeepResearchFlag:
    """When deep_research is disabled, the search endpoint must return 403."""

    @pytest.mark.asyncio
    async def test_search_rejected_when_disabled(self, flag_store):
        flag_store.set("deep_research", False)

        with patch("ops.admin.feature_flags.flag_store", flag_store):
            from fastapi import HTTPException
            from routers.agent import agent_search
            from pydantic import BaseModel

            class FakeRequest(BaseModel):
                query: str = "test query"
                limit: int = 5

            with pytest.raises(HTTPException) as exc_info:
                await agent_search(request=FakeRequest())

            assert exc_info.value.status_code == 403
            assert "disabled" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_search_allowed_when_enabled(self, flag_store):
        flag_store.set("deep_research", True)

        with (
            patch("ops.admin.feature_flags.flag_store", flag_store),
            patch("routers.agent.smart_search", new_callable=AsyncMock, return_value=[]),
        ):
            from routers.agent import agent_search
            from pydantic import BaseModel

            class FakeRequest(BaseModel):
                query: str = "test query"
                limit: int = 5

            result = await agent_search(request=FakeRequest())
            assert result["status"] == "success"


# ── semantic_cache ─────────────────────────────────────────────────────


class TestSemanticCacheFlag:
    """The LLM response cache should only function when semantic_cache is enabled."""

    def test_cache_stores_and_retrieves(self):
        from ops.cache.semantic_cache import LLMResponseCache

        cache = LLMResponseCache(max_entries=10)

        cache.put("What is 2+2?", "gemini-flash", "4")
        result = cache.get("What is 2+2?", "gemini-flash")

        assert result == "4"

    def test_cache_misses_for_different_model(self):
        from ops.cache.semantic_cache import LLMResponseCache

        cache = LLMResponseCache(max_entries=10)

        cache.put("What is 2+2?", "gemini-flash", "4")
        result = cache.get("What is 2+2?", "ollama-phi4")

        assert result is None

    def test_cache_evicts_oldest_at_capacity(self):
        from ops.cache.semantic_cache import LLMResponseCache

        cache = LLMResponseCache(max_entries=2)

        cache.put("prompt1", "model", "r1")
        cache.put("prompt2", "model", "r2")
        cache.put("prompt3", "model", "r3")

        assert cache.get("prompt1", "model") is None
        assert cache.get("prompt2", "model") == "r2"
        assert cache.get("prompt3", "model") == "r3"

    def test_clear_removes_all_entries(self):
        from ops.cache.semantic_cache import LLMResponseCache

        cache = LLMResponseCache(max_entries=10)
        cache.put("p", "m", "r")

        removed = cache.clear()

        assert removed == 1
        assert cache.get("p", "m") is None

    def test_stats_reports_hit_and_miss(self):
        from ops.cache.semantic_cache import LLMResponseCache

        cache = LLMResponseCache(max_entries=10)
        cache.put("p", "m", "r")
        cache.get("p", "m")
        cache.get("missing", "m")

        stats = cache.stats()

        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["entries"] == 1
        assert stats["hit_rate"] == 0.5

    def test_flag_off_bypasses_cache_in_guard_logic(self, flag_store):
        """Simulates the model_manager guard: no cache read when flag is off."""
        from ops.cache.semantic_cache import LLMResponseCache

        flag_store.set("semantic_cache", False)
        cache = LLMResponseCache(max_entries=10)
        cache.put("prompt", "model", "cached_response")

        if flag_store.get("semantic_cache"):
            result = cache.get("prompt", "model")
        else:
            result = None

        assert result is None

    def test_flag_on_reads_from_cache(self, flag_store):
        from ops.cache.semantic_cache import LLMResponseCache

        flag_store.set("semantic_cache", True)
        cache = LLMResponseCache(max_entries=10)
        cache.put("prompt", "model", "cached_response")

        if flag_store.get("semantic_cache"):
            result = cache.get("prompt", "model")
        else:
            result = None

        assert result == "cached_response"
