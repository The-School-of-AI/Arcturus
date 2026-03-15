"""
Three-Tier Execution Router

Routes requests based on content type and requirements:
- Tier 1: Direct HTTP fetch (~50ms, zero browser overhead)
- Tier 2: Headless browser (JS rendering, public content)
- Tier 3: Headful browser (auth, stealth, detection-sensitive)
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
import hashlib
import re
import urllib3
from bs4 import BeautifulSoup


class ExecutionTier(Enum):
    """Execution mode classification"""
    HTTP_FETCH = "http_fetch"  # Direct HTTP, ~50ms
    HEADLESS_BROWSER = "headless_browser"  # JS rendering
    HEADFUL_BROWSER = "headful_browser"  # Auth + stealth


@dataclass
class RouteDecision:
    """Result of routing analysis"""
    tier: ExecutionTier
    confidence: float  # 0.0-1.0
    reasoning: str
    estimated_latency_ms: int
    requires_js: bool
    requires_auth: bool
    requires_stealth: bool
    cost_multiplier: float  # 1.0 (HTTP) to 100.0 (headful + proxy)
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class ExecutionRouter:
    """
    Intelligently routes requests to optimal execution tier.
    
    Analyzes URLs, content requirements, and previous failures to determine
    whether to use HTTP, headless browser, or headful browser.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.history: List[Dict[str, Any]] = []
        
        # Tier costs (relative multipliers)
        self.costs = {
            ExecutionTier.HTTP_FETCH: 1.0,
            ExecutionTier.HEADLESS_BROWSER: 5.0,
            ExecutionTier.HEADFUL_BROWSER: 100.0,
        }
        
        # Latency estimates (milliseconds)
        self.latencies = {
            ExecutionTier.HTTP_FETCH: 50,
            ExecutionTier.HEADLESS_BROWSER: 2000,
            ExecutionTier.HEADFUL_BROWSER: 5000,
        }
        
        # Patterns requiring JS rendering
        self.js_indicators = [
            r'<noscript>',
            r'window\.',
            r'React\.',
            r'Vue\.',
            r'data-react',
            r'ng-',
            r'v-',
            r'__NEXT_DATA__',
        ]
        
        # Patterns requiring auth
        self.auth_indicators = [
            r'login',
            r'sign-in',
            r'authenticate',
            r'oauth',
            r'saml',
            r'jwt',
            r'session',
        ]
        
        # Sites requiring stealth (anti-bot)
        self.stealth_required_domains = [
            'cloudflare',
            'incapsula',
            'akamai',
            'amazon',
            'linkedin',
            'twitter',
            'instagram',
            'facebook',
            'banking',
            'airlines',
            'hotels',
        ]
    
    def route(self, url: str, context: Optional[Dict[str, Any]] = None) -> RouteDecision:
        """
        Route a request to the optimal execution tier.
        
        Args:
            url: Target URL
            context: Optional context (previous failures, user preferences, etc.)
        
        Returns:
            RouteDecision with tier assignment and reasoning
        """
        context = context or {}
        
        # Check for explicit tier override
        if 'force_tier' in context:
            tier = context['force_tier']
            return RouteDecision(
                tier=tier,
                confidence=1.0,
                reasoning="Explicit tier override by user",
                estimated_latency_ms=self.latencies[tier],
                requires_js=True,
                requires_auth=False,
                requires_stealth=False,
                cost_multiplier=self.costs[tier],
            )
        
        # Analyze requirements
        requires_js = self._detect_js_requirement(url, context)
        requires_auth = self._detect_auth_requirement(url, context)
        requires_stealth = self._detect_stealth_requirement(url, context)
        
        # Previous failure history
        previous_failures = context.get('previous_failures', [])
        
        # Route decision logic
        if requires_stealth:
            tier = ExecutionTier.HEADFUL_BROWSER
            confidence = 0.95
            reasoning = "Stealth required (anti-bot site detected)"
        elif requires_auth:
            tier = ExecutionTier.HEADFUL_BROWSER
            confidence = 0.90
            reasoning = "Authentication required"
        elif requires_js or len(previous_failures) > 0:
            tier = ExecutionTier.HEADLESS_BROWSER
            confidence = 0.85
            reasoning = f"JS rendering needed or previous HTTP failure ({len(previous_failures)} attempts)"
        else:
            tier = ExecutionTier.HTTP_FETCH
            confidence = 0.95
            reasoning = "Static content, HTTP sufficient"
        
        decision = RouteDecision(
            tier=tier,
            confidence=confidence,
            reasoning=reasoning,
            estimated_latency_ms=self.latencies[tier],
            requires_js=requires_js,
            requires_auth=requires_auth,
            requires_stealth=requires_stealth,
            cost_multiplier=self.costs[tier],
        )
        
        # Track decision for analytics
        self.history.append({
            'url': url,
            'decision': decision,
            'timestamp': datetime.utcnow(),
        })
        
        return decision
    
    def _detect_js_requirement(self, url: str, context: Dict[str, Any]) -> bool:
        """Detect if URL requires JavaScript rendering"""
        # Check explicit hint
        if context.get('requires_js'):
            return True
        
        # Heuristics
        if 'spa' in url.lower() or 'app' in url.lower():
            return True
        
        # Check if previous HTTP attempt failed
        if context.get('previous_failures', []):
            return True
        
        return False
    
    def _detect_auth_requirement(self, url: str, context: Dict[str, Any]) -> bool:
        """Detect if URL requires authentication"""
        if context.get('requires_auth'):
            return True
        
        # Pattern matching
        for pattern in self.auth_indicators:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        
        return False
    
    def _detect_stealth_requirement(self, url: str, context: Dict[str, Any]) -> bool:
        """Detect if URL requires stealth (anti-bot detection evasion)"""
        if context.get('requires_stealth'):
            return True
        
        # Check domain against stealth-required list
        for domain in self.stealth_required_domains:
            if domain in url.lower():
                return True
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get router statistics"""
        tier_counts = {}
        for entry in self.history:
            tier = entry['decision'].tier.value
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        
        total_cost = sum(
            entry['decision'].cost_multiplier 
            for entry in self.history
        )
        
        return {
            'total_routes': len(self.history),
            'tier_distribution': tier_counts,
            'total_cost_multiplier': total_cost,
            'avg_cost_per_route': total_cost / len(self.history) if self.history else 0,
            'estimated_savings_vs_headful': (
                len(self.history) * 100.0 - total_cost
            ) / (len(self.history) * 100.0) * 100 if self.history else 0,
        }
