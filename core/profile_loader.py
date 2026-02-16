
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

class ProfileLoader:
    """
    Loads and parses the Cortex-R profile configuration from yaml.
    Provides easy access to biases and strategies.
    """
    def __init__(self, profile_path: Optional[str] = None):
        if profile_path:
            self.path = Path(profile_path)
        else:
            # Default path
            self.path = Path(__file__).parent.parent / "config" / "profiles.yaml"
            
        self.data: Dict[str, Any] = {}
        self._load()

    def _load(self):
        if not self.path.exists():
            # Fallback/Default data if file missing
            self.data = {
                "persona": {"tone": "direct", "verbosity": "medium"},
                "strategy": {"max_steps": 3, "planning_mode": "conservative"}
            }
            return

        try:
            with open(self.path, "r") as f:
                self.data = yaml.safe_load(f) or {}
        except Exception:
            self.data = {}

    @property
    def persona(self) -> Dict[str, Any]:
        return self.data.get("persona", {})

    @property
    def strategy(self) -> Dict[str, Any]:
        return self.data.get("strategy", {})

    @property
    def biases(self) -> Dict[str, Any]:
        """
        Aliasing persona attributes to 'biases' as per requirements.
        Maps 'tone' to 'conciseness' if matches.
        """
        persona = self.persona
        return {
            "tone": persona.get("tone", "direct"),
            "verbosity": persona.get("verbosity", "medium"),
            "conciseness": persona.get("tone") == "concise"
        }

    def get(self, key_path: str, default: Any = None) -> Any:
        """Helper to get nested values like 'strategy.max_steps'"""
        parts = key_path.split(".")
        val = self.data
        for part in parts:
            if isinstance(val, dict):
                val = val.get(part)
            else:
                return default
        return val if val is not None else default

# Singleton instance for the system
_loader = None

def get_profile() -> ProfileLoader:
    global _loader
    if _loader is None:
        _loader = ProfileLoader()
    return _loader
