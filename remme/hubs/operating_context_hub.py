"""
OperatingContextHub - Environment and system facts.

Manages what is feasible in the user's environment:
- OS, shell, hardware constraints
- Developer posture (languages, tools)
- Service access (cloud, databases, AI)
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import platform
import os

from remme.hubs.base_hub import BaseHub
from remme.schemas.hub_schemas import (
    OperatingContextHubSchema,
    ConfidenceField,
)


class OperatingContextHub(BaseHub):
    """
    Operating context hub for environment facts.
    
    Controls what assumptions the assistant can make about the user's
    environment: OS, hardware, tooling, and service access.
    """
    
    SCHEMA_CLASS = OperatingContextHubSchema
    DEFAULT_PATH = "memory/user_model/operating_context_hub.json"
    
    def __init__(self, path: Optional[Path] = None):
        super().__init__(path)
        # Auto-detect system info on first load if not present
        if self.data.environment.os.value is None:
            self._auto_detect_system()
    
    def _auto_detect_system(self):
        """Auto-detect basic system information."""
        # Detect OS
        os_name = platform.system().lower()
        os_map = {"darwin": "macos", "linux": "linux", "windows": "windows"}
        self.data.environment.os.value = os_map.get(os_name, os_name)
        self.data.environment.os.version = platform.version()
        self.data.environment.os.confidence = 0.95
        self.data.environment.os.inferred_from = ["system_api"]
        self.data.environment.os.last_seen_at = datetime.now()
        
        # Detect shell
        shell = os.environ.get("SHELL", "")
        if "zsh" in shell:
            shell_name = "zsh"
        elif "bash" in shell:
            shell_name = "bash"
        elif "fish" in shell:
            shell_name = "fish"
        else:
            shell_name = shell.split("/")[-1] if shell else None
        
        if shell_name:
            self.data.environment.shell.value = shell_name
            self.data.environment.shell.confidence = 0.9
            self.data.environment.shell.inferred_from = ["SHELL_env"]
            self.data.environment.shell.last_seen_at = datetime.now()
        
        # Detect CPU architecture
        machine = platform.machine().lower()
        if "arm" in machine or "aarch" in machine:
            self.data.environment.hardware.cpu.architecture = "arm64"
            if os_name == "darwin":
                self.data.environment.hardware.cpu.brand = "apple_silicon"
        elif "x86_64" in machine or "amd64" in machine:
            self.data.environment.hardware.cpu.architecture = "x86_64"
            self.data.environment.hardware.cpu.brand = "intel"
        
        self.data.environment.hardware.cpu.confidence = 0.9
        self.data.environment.hardware.cpu.inferred_from = ["platform_api"]
        self.data.environment.hardware.cpu.last_seen_at = datetime.now()
        
        # Update meta
        self.data.meta.evidence_count += 1
        self.data.meta.confidence = 0.8
        self.data.meta.last_updated = datetime.now()
        if not self.data.meta.created_at:
            self.data.meta.created_at = datetime.now()
        
        print(f"🔍 Auto-detected: {self.data.environment.os.value}, {shell_name}, {machine}")
    
    # =========================================================================
    # RETRIEVAL METHODS
    # =========================================================================
    
    def get_os(self) -> Optional[str]:
        """Get the detected operating system."""
        return self.data.environment.os.value
    
    def get_shell(self) -> Optional[str]:
        """Get the detected shell."""
        return self.data.environment.shell.value
    
    def get_cpu_architecture(self) -> Optional[str]:
        """Get CPU architecture (arm64/x86_64)."""
        return self.data.environment.hardware.cpu.architecture
    
    def get_package_manager(self, language: str) -> Optional[str]:
        """Get preferred package manager for a language."""
        pm = self.data.developer_posture.package_managers.get(language)
        if pm:
            return pm.value
        return None
    
    def get_primary_languages(self) -> List[str]:
        """Get ranked list of primary languages."""
        return self.data.developer_posture.primary_languages.ranked or []
    
    def has_gpu(self) -> bool:
        """Check if GPU is available."""
        gpu = self.data.environment.hardware.gpu.value
        return gpu is not None and gpu not in ["none", "unknown"]
    
    def get_assumption_limits(self) -> Dict[str, bool]:
        """Get assumption limits."""
        limits = self.data.assumption_limits
        return {
            "avoid_cuda": limits.avoid_cuda_unless_confirmed,
            "avoid_docker": limits.avoid_docker_unless_confirmed,
            "avoid_cloud_cli": limits.avoid_cloud_cli_unless_confirmed,
            "prefer_cross_platform": limits.prefer_cross_platform_commands,
        }
    
    def get_context_for_agent(self) -> Dict[str, Any]:
        """
        Get relevant context for agent prompts.
        
        Returns a subset of context that agents should be aware of.
        """
        return {
            "os": self.get_os(),
            "shell": self.get_shell(),
            "architecture": self.get_cpu_architecture(),
            "primary_languages": self.get_primary_languages()[:3],
            "package_managers": {
                "python": self.get_package_manager("python"),
                "javascript": self.get_package_manager("javascript"),
            },
            "has_gpu": self.has_gpu(),
            "assumption_limits": self.get_assumption_limits(),
        }
    
    def get_compact_policy(self, scope: str = "general") -> str:
        """Get compact context summary for prompt injection."""
        os_info = self.get_os() or "unknown"
        shell = self.get_shell() or "unknown"
        arch = self.get_cpu_architecture() or "unknown"
        langs = ", ".join(self.get_primary_languages()[:2]) or "unknown"
        
        lines = [
            f"Environment: {os_info} ({arch}), shell: {shell}",
            f"Languages: {langs}",
        ]
        
        # Add key constraints
        limits = self.get_assumption_limits()
        if limits.get("avoid_cuda"):
            lines.append("GPU: Unknown (avoid CUDA unless confirmed)")
        
        return "\n".join(lines)
    
    # =========================================================================
    # UPDATE METHODS
    # =========================================================================
    
    def set_os(self, value: str, version: Optional[str] = None, evidence: str = "user_statement"):
        """Set operating system."""
        self.data.environment.os.value = value
        if version:
            self.data.environment.os.version = version
        self.data.environment.os.confidence = 0.9
        self.data.environment.os.inferred_from = [evidence]
        self.data.environment.os.last_seen_at = datetime.now()
        self.data.meta.evidence_count += 1
        self._update_confidence()
        print(f"🖥️ Set OS = {value}")
    
    def set_package_manager(self, language: str, manager: str, evidence: str = "user_statement"):
        """Set package manager for a language."""
        if language not in self.data.developer_posture.package_managers:
            self.data.developer_posture.package_managers[language] = ConfidenceField()
        
        pm = self.data.developer_posture.package_managers[language]
        pm.value = manager
        pm.confidence = 0.8
        pm.inferred_from = [evidence]
        pm.last_seen_at = datetime.now()
        
        self.data.meta.evidence_count += 1
        self._update_confidence()
        print(f"📦 Set {language} package manager = {manager}")
    
    def add_primary_language(self, language: str, evidence: str = "project_context"):
        """Add a primary language."""
        languages = self.data.developer_posture.primary_languages.ranked
        if language not in languages:
            languages.insert(0, language)  # Most recent at front
            self.data.developer_posture.primary_languages.confidence = 0.7
            self.data.developer_posture.primary_languages.inferred_from = [evidence]
            self.data.developer_posture.primary_languages.last_seen_at = datetime.now()
            self.data.meta.evidence_count += 1
            self._update_confidence()
            print(f"🔤 Added primary language: {language}")
    
    def set_gpu(self, value: str, vram_gb: Optional[int] = None, evidence: str = "user_statement"):
        """Set GPU information."""
        self.data.environment.hardware.gpu.value = value
        if vram_gb:
            self.data.environment.hardware.gpu.vram_gb = vram_gb
        self.data.environment.hardware.gpu.confidence = 0.8
        self.data.environment.hardware.gpu.inferred_from = [evidence]
        self.data.environment.hardware.gpu.last_seen_at = datetime.now()
        
        # Update assumption limits
        if value and value not in ["none", "unknown"]:
            self.data.assumption_limits.avoid_cuda_unless_confirmed = False
        
        self.data.meta.evidence_count += 1
        self._update_confidence()
        print(f"🎮 Set GPU = {value}")
    
    def set_docker_available(self, available: bool, evidence: str = "command_output"):
        """Set docker availability."""
        self.data.runtime_environments.docker.version = "available" if available else None
        self.data.runtime_environments.docker.confidence = 0.9
        self.data.assumption_limits.avoid_docker_unless_confirmed = not available
        self.data.meta.evidence_count += 1
        self._update_confidence()
        print(f"🐳 Docker available = {available}")


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_hub: Optional[OperatingContextHub] = None


def get_operating_context_hub() -> OperatingContextHub:
    """Get or create the global OperatingContextHub instance."""
    global _hub
    if _hub is None:
        _hub = OperatingContextHub()
    return _hub
