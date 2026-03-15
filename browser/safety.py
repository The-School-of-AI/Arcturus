"""
P12 Aegis - Phantom Browser Safety Layer
Implements URL validation, content sanitization, and injection defense.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple
from urllib.parse import urlparse


class URLValidator:
    """Validates URLs against security policy."""
    
    # Dangerous schemes
    BLOCKED_SCHEMES = {"file", "data", "javascript", "vbscript"}
    
    # Dangerous domains (local/private)
    BLOCKED_DOMAINS = {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "169.254.169.254",  # AWS metadata
    }
    
    # IP ranges to block (private networks)
    PRIVATE_IP_PATTERNS = [
        r"^10\.",
        r"^172\.(1[6-9]|2[0-9]|3[01])\.",
        r"^192\.168\.",
        r"^127\.",
    ]
    
    @classmethod
    def validate(cls, url: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a URL against security policy.
        
        Returns:
            (is_valid, error_message)
        """
        try:
            parsed = urlparse(url)
            
            # Check scheme
            if parsed.scheme in cls.BLOCKED_SCHEMES:
                return False, f"Blocked scheme: {parsed.scheme}"
            
            # Check hostname
            hostname = parsed.hostname or ""
            
            # Block localhost
            if hostname in cls.BLOCKED_DOMAINS:
                return False, f"Blocked domain: {hostname}"
            
            # Block private IPs
            for pattern in cls.PRIVATE_IP_PATTERNS:
                if re.match(pattern, hostname):
                    return False, f"Blocked private IP: {hostname}"
            
            # Check for obvious attacks
            if ".." in parsed.path:
                return False, "Path traversal detected"
            
            return True, None
        
        except Exception as e:
            return False, f"URL validation error: {str(e)}"


class ContentSanitizer:
    """Sanitizes extracted content to prevent injection attacks."""
    
    # Patterns that indicate prompt injection attempts
    INJECTION_PATTERNS = [
        (r"ignore\s+all\s+previous", "Ignore previous instruction"),
        (r"system\s*:\s*", "System instruction override"),
        (r"override\s+(safety|constraint|guardrail)", "Safety override"),
        (r"assume\s+the\s+role", "Role assumption"),
        (r"you\s+are\s+now", "Identity override"),
        (r"forget\s+", "Memory override"),
        (r"<prompt", "XML prompt tag"),
        (r"\[SYSTEM\]", "System bracket tag"),
        (r"<!DOCTYPE", "HTML doctype"),
    ]
    
    # HTML/JavaScript patterns to remove
    DANGEROUS_PATTERNS = [
        (r"<script[^>]*>.*?</script>", "Script tag", re.DOTALL | re.IGNORECASE),
        (r"<iframe[^>]*>.*?</iframe>", "IFrame tag", re.DOTALL | re.IGNORECASE),
        (r"<embed[^>]*>", "Embed tag", re.IGNORECASE),
        (r"<object[^>]*>", "Object tag", re.IGNORECASE),
        (r"on\w+\s*=\s*['\"]", "Event handler", re.IGNORECASE),
        (r"javascript:", "JavaScript protocol", re.IGNORECASE),
    ]
    
    @classmethod
    def sanitize(cls, content: str) -> Tuple[str, list]:
        """
        Sanitize content by removing dangerous patterns.
        
        Returns:
            (sanitized_content, list_of_removals)
        """
        sanitized = content
        removals = []
        
        # Remove dangerous HTML/JS
        for pattern, description, *flags in cls.DANGEROUS_PATTERNS:
            flag_value = flags[0] if flags else 0
            if re.search(pattern, sanitized, flag_value):
                sanitized = re.sub(pattern, "", sanitized, flags=flag_value)
                removals.append(description)
        
        return sanitized, removals
    
    @classmethod
    def detect_injection(cls, content: str) -> Tuple[bool, list]:
        """
        Detect potential prompt injection attempts.
        
        Returns:
            (is_suspicious, list_of_detected_patterns)
        """
        detected = []
        
        for pattern, description in cls.INJECTION_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                detected.append(description)
        
        return len(detected) > 0, detected


class SafetyPolicy:
    """High-level safety policy enforcement."""
    
    def __init__(self, strict_mode: bool = True):
        """
        Initialize safety policy.
        
        Args:
            strict_mode: If True, reject suspicious content; if False, just warn
        """
        self.strict_mode = strict_mode
    
    def validate_and_sanitize(
        self,
        url: str,
        content: str
    ) -> Tuple[bool, dict]:
        """
        Perform full validation and sanitization.
        
        Returns:
            (is_safe, details_dict)
        """
        details = {
            "url_valid": False,
            "url_error": None,
            "content_sanitized": False,
            "sanitizations": [],
            "injection_detected": False,
            "injection_patterns": [],
            "is_safe": False,
        }
        
        # Validate URL
        url_valid, url_error = URLValidator.validate(url)
        details["url_valid"] = url_valid
        details["url_error"] = url_error
        
        if not url_valid and self.strict_mode:
            details["is_safe"] = False
            return False, details
        
        # Sanitize content
        sanitized, sanitizations = ContentSanitizer.sanitize(content)
        if sanitizations:
            details["content_sanitized"] = True
            details["sanitizations"] = sanitizations
        
        # Detect injection
        is_suspicious, patterns = ContentSanitizer.detect_injection(sanitized)
        if is_suspicious:
            details["injection_detected"] = True
            details["injection_patterns"] = patterns
            if self.strict_mode:
                details["is_safe"] = False
                return False, details
        
        # All checks passed
        details["is_safe"] = True
        return True, details
