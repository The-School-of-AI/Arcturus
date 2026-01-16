"""
User Preference Hub

Manages user preferences as a behavioral policy layer.
Based on the ChatGPT recommendations for preference systems:
- Scope + Priority + Confidence
- Output Contract (tone, structure, emoji)
- Autonomy Gates (clarifications, destructive actions)
- Avoid Patterns (phrases + moves to never use)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


# Default preferences path
PREFERENCES_PATH = Path(__file__).parent.parent / "config" / "user_preferences.json"


@dataclass
class PreferenceUpdate:
    """Represents a preference update command."""
    key: str           # e.g., "output_contract.verbosity.by_scope.coding"
    value: Any         # New value
    scope: str = "global"  # Scope where this applies
    priority: str = "soft"  # hard | soft | situational
    evidence: str = ""     # What triggered this update


class UserPreferenceHub:
    """
    Central hub for user preferences.
    
    Provides:
    - Load/save preferences from JSON
    - Scope-based preference retrieval
    - Update with confidence tracking
    - Agent-specific policy extraction
    """
    
    def __init__(self, path: Path = None):
        self.path = path or PREFERENCES_PATH
        self.preferences = self._load()
    
    def _load(self) -> Dict[str, Any]:
        """Load preferences from JSON file."""
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except Exception as e:
                print(f"⚠️ Failed to load preferences: {e}")
        return self._default_preferences()
    
    def _default_preferences(self) -> Dict[str, Any]:
        """Return default preference structure."""
        return {
            "output_contract": {
                "verbosity": {"default": "concise", "by_scope": {}},
                "format_defaults": {"default": "markdown", "by_scope": {}},
                "structure_rules": [],
                "tone_constraints": [],
                "emoji_policy": "minimal",
                "chunking": {"max_lines": 400, "prefer_full_files": True}
            },
            "avoid_patterns": {"phrases": [], "moves": []},
            "coding_style": {
                "default_language": "python",
                "style": "mixed",
                "comment_density": "low",
                "deliverable_preference": "full_file",
                "type_annotations": True
            },
            "tooling_defaults": {
                "frameworks": [],
                "package_manager": {"python": "pip", "javascript": "npm"},
                "validation": [],
                "testing": []
            },
            "planning_policy": {
                "clarifications": "normal",
                "options_mode": "single_best",
                "safe_assumptions_ok": True,
                "autonomy": {
                    "create_files": "allowed",
                    "run_shell": "allowed",
                    "destructive_actions": "confirm_first",
                    "web_browse": "allowed"
                },
                "risk_tolerance": {"default": "moderate", "by_scope": {}}
            },
            "interaction_style": {
                "decision_style": "single_best",
                "iteration_style": "fast_iterations",
                "feedback_style": "implicit_ok"
            },
            "meta": {
                "version": "1.0",
                "confidence": 0.0,
                "evidence_count": 0,
                "last_updated": None,
                "created_at": datetime.now().isoformat()
            }
        }
    
    def save(self):
        """Save preferences to JSON file."""
        self.preferences["meta"]["last_updated"] = datetime.now().isoformat()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.preferences, indent=2))
        print(f"💾 Preferences saved to {self.path}")
    
    # =========================================================================
    # RETRIEVAL METHODS
    # =========================================================================
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a preference by dotted key path.
        
        Example: hub.get("output_contract.verbosity.default")
        """
        keys = key.split(".")
        value = self.preferences
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def get_for_scope(self, category: str, field: str, scope: str) -> Any:
        """
        Get a preference for a specific scope, falling back to default.
        
        Example: hub.get_for_scope("output_contract", "verbosity", "coding")
        Returns the coding-specific verbosity or the default if not set.
        """
        cat = self.preferences.get(category, {})
        field_data = cat.get(field, {})
        
        if isinstance(field_data, dict):
            by_scope = field_data.get("by_scope", {})
            if scope in by_scope:
                return by_scope[scope]
            return field_data.get("default")
        return field_data
    
    def get_policy_for_agent(self, agent_type: str) -> Dict[str, Any]:
        """
        Get relevant preferences for a specific agent type.
        
        Returns a filtered subset of preferences that the agent should use.
        """
        # Map agent types to scopes
        scope_map = {
            "PlannerAgent": "planning",
            "CoderAgent": "coding",
            "DistillerAgent": "coding",
            "FormatterAgent": "formatting",
            "RetrieverAgent": "research",
            "ThinkerAgent": "reasoning",
            "ClarificationAgent": "clarification",
        }
        scope = scope_map.get(agent_type, "general")
        
        policy = {
            "verbosity": self.get_for_scope("output_contract", "verbosity", scope),
            "format": self.get_for_scope("output_contract", "format_defaults", scope),
            "tone_constraints": self.get("output_contract.tone_constraints", []),
            "avoid_patterns": self.get("avoid_patterns", {}),
            "clarifications": self.get("planning_policy.clarifications", "normal"),
            "autonomy": self.get("planning_policy.autonomy", {}),
        }
        
        # Add agent-specific preferences
        if agent_type in ["CoderAgent", "DistillerAgent"]:
            policy["coding_style"] = self.get("coding_style", {})
            policy["tooling"] = self.get("tooling_defaults", {})
        
        return policy
    
    def get_compact_policy(self, scope: str = "general") -> str:
        """
        Get a compact text summary for prompt injection (< 100 tokens).
        """
        verbosity = self.get_for_scope("output_contract", "verbosity", scope) or "concise"
        clarifications = self.get("planning_policy.clarifications", "normal")
        tone = ", ".join(self.get("output_contract.tone_constraints", [])[:2])
        avoid = ", ".join(self.get("avoid_patterns.phrases", [])[:2])
        
        lines = [
            f"User prefers: {verbosity} responses",
            f"Clarifications: {clarifications}",
        ]
        if tone:
            lines.append(f"Tone: {tone}")
        if avoid:
            lines.append(f"Avoid: {avoid}")
        
        return "\n".join(lines)
    
    # =========================================================================
    # UPDATE METHODS
    # =========================================================================
    
    def update(self, key: str, value: Any, evidence: str = ""):
        """
        Update a preference by dotted key path.
        
        Increments evidence_count and confidence.
        """
        keys = key.split(".")
        target = self.preferences
        
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        
        target[keys[-1]] = value
        
        # Update meta
        self.preferences["meta"]["evidence_count"] += 1
        old_conf = self.preferences["meta"]["confidence"]
        # Asymptotic confidence increase
        self.preferences["meta"]["confidence"] = min(1.0, old_conf + (1 - old_conf) * 0.1)
        
        print(f"📝 Updated preference: {key} = {value}")
        if evidence:
            print(f"   Evidence: {evidence}")
    
    def add_avoid_phrase(self, phrase: str, priority: str = "hard"):
        """Add a phrase to the avoid list."""
        phrases = self.preferences.setdefault("avoid_patterns", {}).setdefault("phrases", [])
        if phrase not in phrases:
            phrases.append(phrase)
            self.preferences["meta"]["evidence_count"] += 1
            print(f"🚫 Added avoid phrase: '{phrase}'")
    
    def add_structure_rule(self, rule: str):
        """Add a structure rule."""
        rules = self.preferences.setdefault("output_contract", {}).setdefault("structure_rules", [])
        if rule not in rules:
            rules.append(rule)
            print(f"📋 Added structure rule: '{rule}'")
    
    def set_scope_preference(self, category: str, field: str, scope: str, value: Any):
        """
        Set a scope-specific preference.
        
        Example: hub.set_scope_preference("output_contract", "verbosity", "teaching", "detailed")
        """
        cat = self.preferences.setdefault(category, {})
        field_data = cat.setdefault(field, {"default": None, "by_scope": {}})
        
        if isinstance(field_data, dict):
            field_data.setdefault("by_scope", {})[scope] = value
        
        print(f"🎯 Set {category}.{field} for scope '{scope}' = {value}")


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_hub: Optional[UserPreferenceHub] = None


def get_preference_hub() -> UserPreferenceHub:
    """Get or create the global preference hub instance."""
    global _hub
    if _hub is None:
        _hub = UserPreferenceHub()
    return _hub


def get_policy_for_agent(agent_type: str) -> Dict[str, Any]:
    """Convenience function to get agent-specific policy."""
    return get_preference_hub().get_policy_for_agent(agent_type)


def get_compact_policy(scope: str = "general") -> str:
    """Convenience function to get compact policy text."""
    return get_preference_hub().get_compact_policy(scope)
