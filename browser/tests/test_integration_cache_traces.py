"""Integration tests for Cache and Tracing"""
import pytest
from browser.core.action_cache import ActionCache


class TestActionCacheIntegrationScenarios:
    """Test realistic cache scenarios"""
    
    def test_multi_page_caching(self):
        """Test caching across multiple pages"""
        cache = ActionCache()
        
        pages = [
            {
                "url": "https://example.com/page1",
                "title": "Page 1",
                "dom_hash": "page1_hash",
                "critical_elements": [{"id": "button1"}]
            },
            {
                "url": "https://example.com/page2",
                "title": "Page 2",
                "dom_hash": "page2_hash",
                "critical_elements": [{"id": "button2"}]
            },
            {
                "url": "https://example.com/page3",
                "title": "Page 3",
                "dom_hash": "page3_hash",
                "critical_elements": [{"id": "button3"}]
            },
        ]
        
        # Cache actions for each page
        for page in pages:
            page_hash = cache.compute_page_hash(page)
            cache.cache_action(
                page_hash=page_hash,
                action_type="click",
                parameters={"selector": f"#{page.get('dom_hash')}"},
                result="Action completed"
            )
        
        # Verify all are cached
        for page in pages:
            page_hash = cache.compute_page_hash(page)
            action = cache.get_cached_action(page_hash, "click")
            assert action is not None
    
    def test_page_update_detection(self):
        """Test detecting page updates via hash"""
        cache = ActionCache()
        
        # Original page state
        page_state_v1 = {
            "url": "https://example.com",
            "title": "Example",
            "dom_hash": "abc123",
            "critical_elements": []
        }
        hash_v1 = cache.compute_page_hash(page_state_v1)
        
        # Cache action
        cache.cache_action(
            page_hash=hash_v1,
            action_type="click",
            parameters={"selector": "#button"},
            result="Success"
        )
        
        # Updated page state
        page_state_v2 = {
            "url": "https://example.com",
            "title": "Example Updated",
            "dom_hash": "xyz789",
            "critical_elements": []
        }
        hash_v2 = cache.compute_page_hash(page_state_v2)
        
        # Invalidate old cache when page updates
        invalidated = cache.invalidate_page_cache(hash_v1, hash_v2)
        assert invalidated >= 0
        
        # Old cache should be gone
        old_action = cache.get_cached_action(hash_v1, "click")
        assert old_action is None


class TestCacheStatisticsTracking:
    """Test cache statistics and metrics"""
    
    def test_cache_efficiency_metrics(self):
        """Test that cache provides efficiency metrics"""
        cache = ActionCache()
        
        # Create pages and cache actions
        for i in range(5):
            page_state = {
                "url": f"https://example.com/page{i}",
                "title": f"Page {i}",
                "dom_hash": f"hash_{i}",
                "critical_elements": []
            }
            page_hash = cache.compute_page_hash(page_state)
            cache.cache_action(
                page_hash=page_hash,
                action_type="click",
                parameters={"selector": f"#button{i}"},
                result=f"Result {i}"
            )
        
        # Get statistics
        stats = cache.get_cache_statistics()
        assert stats is not None
        assert isinstance(stats, dict)
        # Should have some metrics
        assert len(stats) > 0


class TestActionCacheReplay:
    """Test replaying cached actions"""
    
    def test_cache_replay_flow(self):
        """Test the flow of caching then replaying"""
        cache = ActionCache()
        
        # Initial page state
        page_state = {
            "url": "https://example.com/form",
            "title": "Form Page",
            "dom_hash": "form_v1",
            "critical_elements": []
        }
        page_hash = cache.compute_page_hash(page_state)
        
        # First visit: perform action
        action_id = cache.cache_action(
            page_hash=page_hash,
            action_type="type",
            parameters={"selector": "#username", "value": "john"},
            result="Text entered"
        )
        assert action_id is not None
        
        # Later visit: replay from cache
        cached_action = cache.get_cached_action(page_hash, "type")
        assert cached_action is not None
        assert cached_action.action_type == "type"
        assert cached_action.parameters["value"] == "john"
