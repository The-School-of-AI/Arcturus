"""
Base Hub - Abstract base class for all UserModel hubs.

Provides common functionality for:
- JSON persistence with automatic directory creation
- Confidence tracking and decay
- Evidence-based updates
- Scope-based value retrieval
"""

import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Type, TypeVar

from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


class BaseHub(ABC):
    """Abstract base class for all UserModel hubs."""
    
    # Subclasses must define these
    SCHEMA_CLASS: Type[BaseModel] = None
    DEFAULT_PATH: str = None
    
    def __init__(self, path: Optional[Path] = None):
        """
        Initialize the hub.
        
        Args:
            path: Optional path to the hub's JSON file. 
                  If None, uses DEFAULT_PATH relative to project root.
        """
        if path:
            self.path = Path(path)
        elif self.DEFAULT_PATH:
            self.path = Path(__file__).parent.parent.parent / self.DEFAULT_PATH
        else:
            raise ValueError(f"{self.__class__.__name__} must define DEFAULT_PATH or receive a path")
        
        self.data: BaseModel = self._load()
    
    def _load(self) -> BaseModel:
        """Load hub data from JSON file."""
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text())
                return self.SCHEMA_CLASS(**raw)
            except Exception as e:
                print(f"⚠️ Failed to load {self.__class__.__name__}: {e}")
        return self.SCHEMA_CLASS()
    
    def save(self):
        """Save hub data to JSON file."""
        # Update meta timestamp
        if hasattr(self.data, 'meta') and hasattr(self.data.meta, 'last_updated'):
            self.data.meta.last_updated = datetime.now()
            if not self.data.meta.created_at:
                self.data.meta.created_at = datetime.now()
        
        # Ensure directory exists
        self.path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write JSON with datetime serialization
        self.path.write_text(self.data.model_dump_json(indent=2))
        print(f"💾 Saved {self.__class__.__name__} to {self.path}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value by dot-separated key path.
        
        Example: hub.get("output_contract.verbosity.default")
        """
        keys = key.split(".")
        value = self.data
        try:
            for k in keys:
                if isinstance(value, BaseModel):
                    value = getattr(value, k, None)
                elif isinstance(value, dict):
                    value = value.get(k)
                else:
                    return default
                if value is None:
                    return default
            return value
        except (AttributeError, KeyError):
            return default
    
    def set(self, key: str, value: Any, evidence: Optional[str] = None):
        """
        Set a value by dot-separated key path.
        
        Example: hub.set("output_contract.verbosity.default", "concise")
        """
        keys = key.split(".")
        target = self.data
        
        for k in keys[:-1]:
            if isinstance(target, BaseModel):
                target = getattr(target, k, None)
            elif isinstance(target, dict):
                target = target.get(k)
            else:
                raise ValueError(f"Cannot traverse to {key}: {k} is not accessible")
        
        final_key = keys[-1]
        if isinstance(target, BaseModel):
            setattr(target, final_key, value)
        elif isinstance(target, dict):
            target[final_key] = value
        else:
            raise ValueError(f"Cannot set {key}: parent is not a model or dict")
        
        # Update meta
        if hasattr(self.data, 'meta'):
            self.data.meta.evidence_count += 1
            self._update_confidence()
        
        print(f"📝 Updated {key} = {value}")
        if evidence:
            print(f"   Evidence: {evidence}")
    
    def _update_confidence(self):
        """Update overall confidence using asymptotic formula."""
        if hasattr(self.data, 'meta'):
            old_conf = self.data.meta.confidence
            # Asymptotic increase: new = old + (1 - old) * increment
            self.data.meta.confidence = min(1.0, old_conf + (1 - old_conf) * 0.1)
    
    def get_for_scope(self, field_path: str, scope: str) -> Any:
        """
        Get a scoped value, falling back to default.
        
        Example: hub.get_for_scope("output_contract.verbosity", "coding")
        """
        field = self.get(field_path)
        if field is None:
            return None
        
        # Try scope-specific value first
        if hasattr(field, 'by_scope'):
            by_scope = getattr(field, 'by_scope', {})
            if isinstance(by_scope, dict) and scope in by_scope:
                return by_scope[scope]
        
        # Fall back to default
        if hasattr(field, 'default'):
            return getattr(field, 'default', None)
        
        return field
    
    def set_for_scope(self, field_path: str, scope: str, value: Any):
        """
        Set a scope-specific value.
        
        Example: hub.set_for_scope("output_contract.verbosity", "coding", "concise")
        """
        field = self.get(field_path)
        if field is None:
            raise ValueError(f"Field {field_path} does not exist")
        
        if hasattr(field, 'by_scope'):
            by_scope = getattr(field, 'by_scope', {})
            if isinstance(by_scope, dict):
                by_scope[scope] = value
                self.data.meta.evidence_count += 1
                self._update_confidence()
                print(f"🎯 Set {field_path} for scope '{scope}' = {value}")
                return
        
        raise ValueError(f"Field {field_path} does not support scopes")
    
    def to_dict(self) -> Dict[str, Any]:
        """Return hub data as a dictionary."""
        return self.data.model_dump()
    
    def reload(self):
        """Reload hub data from disk."""
        self.data = self._load()
    
    @abstractmethod
    def get_compact_policy(self, scope: str = "general") -> str:
        """
        Get a compact text summary for prompt injection.
        
        Should return a concise string (< 100 tokens) suitable for
        injecting into agent prompts.
        """
        pass
