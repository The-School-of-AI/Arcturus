"""
Circuit Breaker Pattern Implementation

Provides resilience for external service calls by failing fast when
services are experiencing issues.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Service is failing, reject requests immediately  
- HALF_OPEN: Testing if service has recovered
"""

import time
from enum import Enum
from threading import Lock
from typing import Dict, Optional
from dataclasses import dataclass, field


class CircuitState(Enum):
    CLOSED = "closed"      # Normal - requests go through
    OPEN = "open"          # Failing - reject fast
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for a single service/tool.
    
    Usage:
        breaker = get_breaker("duckduckgo_search")
        if breaker.can_execute():
            try:
                result = await call_service()
                breaker.record_success()
            except Exception:
                breaker.record_failure()
        else:
            raise CircuitOpenError("Service temporarily unavailable")
    """
    name: str
    failure_threshold: int = 5          # Failures before opening
    recovery_timeout: float = 60.0      # Seconds before trying HALF_OPEN
    half_open_max_calls: int = 2        # Test calls in HALF_OPEN state
    
    # Internal state
    state: CircuitState = field(default=CircuitState.CLOSED)
    failure_count: int = field(default=0)
    success_count: int = field(default=0)
    last_failure_time: float = field(default=0.0)
    half_open_calls: int = field(default=0)
    _lock: Lock = field(default_factory=Lock)
    
    def can_execute(self) -> bool:
        """Check if a request can proceed."""
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            
            if self.state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if time.time() - self.last_failure_time >= self.recovery_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
                    return True
                return False
            
            if self.state == CircuitState.HALF_OPEN:
                # Allow limited test calls
                if self.half_open_calls < self.half_open_max_calls:
                    self.half_open_calls += 1
                    return True
                return False
            
            return False
    
    def record_success(self):
        """Record a successful call."""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                # If we've had enough successes in HALF_OPEN, close the circuit
                if self.success_count >= self.half_open_max_calls:
                    self._transition_to(CircuitState.CLOSED)
            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success
                self.failure_count = max(0, self.failure_count - 1)
    
    def record_failure(self):
        """Record a failed call."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                # Any failure in HALF_OPEN opens the circuit again
                self._transition_to(CircuitState.OPEN)
            elif self.state == CircuitState.CLOSED:
                if self.failure_count >= self.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
    
    def _transition_to(self, new_state: CircuitState):
        """Transition to a new state with logging."""
        old_state = self.state
        self.state = new_state
        
        if new_state == CircuitState.CLOSED:
            self.failure_count = 0
            self.success_count = 0
            self.half_open_calls = 0
            print(f"⚡ Circuit [{self.name}]: {old_state.value} → CLOSED (recovered)")
        elif new_state == CircuitState.OPEN:
            self.half_open_calls = 0
            self.success_count = 0
            print(f"🔴 Circuit [{self.name}]: {old_state.value} → OPEN (failing fast)")
        elif new_state == CircuitState.HALF_OPEN:
            self.half_open_calls = 0
            self.success_count = 0
            print(f"🟡 Circuit [{self.name}]: {old_state.value} → HALF_OPEN (testing)")
    
    def force_open(self):
        """Manually open the circuit."""
        with self._lock:
            self._transition_to(CircuitState.OPEN)
            self.last_failure_time = time.time()
    
    def force_close(self):
        """Manually close the circuit."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
    
    def get_status(self) -> dict:
        """Get current circuit status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure": self.last_failure_time,
            "time_until_retry": max(0, self.recovery_timeout - (time.time() - self.last_failure_time)) if self.state == CircuitState.OPEN else 0
        }


class CircuitOpenError(Exception):
    """Raised when circuit is open and request is rejected."""
    pass


# ============================================================================
# GLOBAL REGISTRY
# ============================================================================

_breakers: Dict[str, CircuitBreaker] = {}
_registry_lock = Lock()


def get_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0
) -> CircuitBreaker:
    """
    Get or create a circuit breaker for a given name.
    
    Args:
        name: Unique identifier (e.g., tool name, server name)
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds before testing recovery
    
    Returns:
        CircuitBreaker instance
    """
    global _breakers
    with _registry_lock:
        if name not in _breakers:
            _breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout
            )
        return _breakers[name]


def get_all_breakers() -> Dict[str, dict]:
    """Get status of all circuit breakers."""
    return {name: breaker.get_status() for name, breaker in _breakers.items()}


def reset_all_breakers():
    """Reset all circuit breakers to CLOSED state."""
    for breaker in _breakers.values():
        breaker.force_close()
