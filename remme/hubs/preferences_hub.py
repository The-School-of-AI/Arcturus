"""
PreferencesHub - Behavioral policy layer for user preferences.

Manages:
- Output contract (verbosity, format, tone)
- Tooling defaults (frameworks, package managers)
- Autonomy settings (what actions are allowed)
- Anti-preferences (patterns to avoid)
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from remme.hubs.base_hub import BaseHub
from remme.schemas.hub_schemas import (
    PreferencesHubSchema,
    ScopedValue,
)


class PreferencesHub(BaseHub):
    """
    User preferences hub for behavioral policies.
    
    Controls how the assistant behaves: output style, interaction choreography,
    tooling choices, and autonomy gates.
    """
    
    SCHEMA_CLASS = PreferencesHubSchema
    DEFAULT_PATH = "memory/user_model/preferences_hub.json"
    
    def __init__(self, path: Optional[Path] = None):
        super().__init__(path)
    
    # =========================================================================
    # RETRIEVAL METHODS
    # =========================================================================
    
    def get_verbosity(self, scope: str = "general") -> str:
        """Get verbosity preference for a scope."""
        return self.get_for_scope("output_contract.verbosity", scope) or "concise"
    
    def get_format(self, scope: str = "general") -> str:
        """Get format preference for a scope."""
        return self.get_for_scope("output_contract.format_defaults", scope) or "markdown"
    
    def get_tone_constraints(self) -> List[str]:
        """Get list of tone constraints."""
        return self.get("output_contract.tone_constraints") or []
    
    def get_structure_rules(self) -> List[str]:
        """Get list of structure rules."""
        return self.get("output_contract.structure_rules") or []
    
    def get_avoid_patterns(self) -> Dict[str, List[str]]:
        """Get patterns to avoid."""
        patterns = self.get("anti_preferences.avoid_patterns")
        if patterns:
            return {
                "phrases": getattr(patterns, 'phrases', []),
                "moves": getattr(patterns, 'moves', [])
            }
        return {"phrases": [], "moves": []}
    
    def get_clarifications_policy(self) -> str:
        """Get clarification policy."""
        return self.get("output_contract.questions_policy.clarifications") or "minimize"
    
    def get_autonomy(self, action: str) -> str:
        """Get autonomy setting for a specific action."""
        return self.get(f"autonomy_and_risk.autonomy.{action}") or "allowed"
    
    def get_risk_tolerance(self, scope: str = "general") -> str:
        """Get risk tolerance for a scope."""
        risk = self.get("autonomy_and_risk.risk_tolerance")
        if risk:
            by_scope = getattr(risk, 'by_scope', {})
            if isinstance(by_scope, dict) and scope in by_scope:
                return by_scope[scope]
            return getattr(risk, 'default', "moderate")
        return "moderate"
    
    def get_tooling_defaults(self) -> Dict[str, Any]:
        """Get tooling defaults."""
        tooling = self.get("tooling_defaults")
        if tooling:
            return {
                "frameworks": {
                    "frontend": getattr(tooling.frameworks, 'frontend', []),
                    "backend": getattr(tooling.frameworks, 'backend', []),
                    "testing": getattr(tooling.frameworks, 'testing', [])
                },
                "package_manager": {
                    "python": getattr(tooling.package_manager, 'python', 'pip'),
                    "javascript": getattr(tooling.package_manager, 'javascript', 'npm')
                },
                "validation": getattr(tooling, 'validation', []),
                "testing": getattr(tooling, 'testing', [])
            }
        return {}
    
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
            "verbosity": self.get_verbosity(scope),
            "format": self.get_format(scope),
            "tone_constraints": self.get_tone_constraints(),
            "structure_rules": self.get_structure_rules(),
            "avoid_patterns": self.get_avoid_patterns(),
            "clarifications": self.get_clarifications_policy(),
            "autonomy": {
                "create_files": self.get_autonomy("create_files"),
                "run_shell": self.get_autonomy("run_shell"),
                "destructive_actions": self.get_autonomy("destructive_actions"),
            },
            "risk_tolerance": self.get_risk_tolerance(scope),
        }
        
        # Add agent-specific preferences
        if agent_type in ["CoderAgent", "DistillerAgent"]:
            policy["tooling"] = self.get_tooling_defaults()
            policy["coding_style"] = {
                "deliverable_preference": self.get("coding_contracts.deliverable_preference"),
                "type_annotations": self.get("tooling_defaults.style_preferences.type_annotations"),
            }
        
        return policy
    
    def get_compact_policy(self, scope: str = "general") -> str:
        """
        Get a compact text summary for prompt injection (< 100 tokens).
        """
        verbosity = self.get_verbosity(scope)
        clarifications = self.get_clarifications_policy()
        tone = ", ".join(self.get_tone_constraints()[:2])
        avoid = ", ".join(self.get_avoid_patterns().get("phrases", [])[:2])
        
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
    
    def set_verbosity(self, value: str, scope: Optional[str] = None):
        """Set verbosity preference."""
        if scope:
            self.set_for_scope("output_contract.verbosity", scope, value)
        else:
            self.set("output_contract.verbosity.default", value)
    
    def set_format(self, value: str, scope: Optional[str] = None):
        """Set format preference."""
        if scope:
            self.set_for_scope("output_contract.format_defaults", scope, value)
        else:
            self.set("output_contract.format_defaults.default", value)
    
    def add_tone_constraint(self, constraint: str):
        """Add a tone constraint."""
        constraints = self.get_tone_constraints()
        if constraint not in constraints:
            constraints.append(constraint)
            self.data.output_contract.tone_constraints = constraints
            self.data.meta.evidence_count += 1
            self._update_confidence()
            print(f"🎭 Added tone constraint: '{constraint}'")
    
    def add_structure_rule(self, rule: str):
        """Add a structure rule."""
        rules = self.get_structure_rules()
        if rule not in rules:
            rules.append(rule)
            self.data.output_contract.structure_rules = rules
            self.data.meta.evidence_count += 1
            self._update_confidence()
            print(f"📋 Added structure rule: '{rule}'")
    
    def add_avoid_phrase(self, phrase: str):
        """Add a phrase to avoid."""
        phrases = self.data.anti_preferences.avoid_patterns.phrases
        if phrase not in phrases:
            phrases.append(phrase)
            self.data.meta.evidence_count += 1
            self._update_confidence()
            print(f"🚫 Added avoid phrase: '{phrase}'")
    
    def add_avoid_move(self, move: str):
        """Add a move to avoid."""
        moves = self.data.anti_preferences.avoid_patterns.moves
        if move not in moves:
            moves.append(move)
            self.data.meta.evidence_count += 1
            self._update_confidence()
            print(f"🚫 Added avoid move: '{move}'")
    
    def set_autonomy(self, action: str, value: str):
        """Set autonomy setting for an action."""
        if hasattr(self.data.autonomy_and_risk.autonomy, action):
            setattr(self.data.autonomy_and_risk.autonomy, action, value)
            self.data.meta.evidence_count += 1
            self._update_confidence()
            print(f"🔐 Set autonomy for '{action}' = {value}")
        else:
            raise ValueError(f"Unknown autonomy action: {action}")
    
    def set_risk_tolerance(self, value: str, scope: Optional[str] = None):
        """Set risk tolerance."""
        if scope:
            self.data.autonomy_and_risk.risk_tolerance.by_scope[scope] = value
        else:
            self.data.autonomy_and_risk.risk_tolerance.default = value
        self.data.meta.evidence_count += 1
        self._update_confidence()
        print(f"⚠️ Set risk tolerance{' for ' + scope if scope else ''} = {value}")
    
    def set_package_manager(self, language: str, manager: str):
        """Set preferred package manager for a language."""
        if hasattr(self.data.tooling_defaults.package_manager, language):
            setattr(self.data.tooling_defaults.package_manager, language, manager)
            self.data.meta.evidence_count += 1
            self._update_confidence()
            print(f"📦 Set {language} package manager = {manager}")
        else:
            raise ValueError(f"Unknown language for package manager: {language}")
    
    def add_framework(self, category: str, framework: str):
        """Add a preferred framework."""
        if hasattr(self.data.tooling_defaults.frameworks, category):
            frameworks = getattr(self.data.tooling_defaults.frameworks, category)
            if framework not in frameworks:
                frameworks.append(framework)
                self.data.meta.evidence_count += 1
                self._update_confidence()
                print(f"🔧 Added {category} framework: {framework}")
        else:
            raise ValueError(f"Unknown framework category: {category}")


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_hub: Optional[PreferencesHub] = None


def get_preferences_hub() -> PreferencesHub:
    """Get or create the global PreferencesHub instance."""
    global _hub
    if _hub is None:
        _hub = PreferencesHub()
    return _hub
