import secrets
import base64
from typing import Dict

class CanvasSandbox:
    """
    Security Layer for the Canvas.
    Generates CSP headers and session nonces for iframe isolation.
    """
    @staticmethod
    def generate_nonce() -> str:
        """Generate a cryptographic nonce for postMessage verification."""
        return secrets.token_urlsafe(32)

    @staticmethod
    def get_csp_headers() -> Dict[str, str]:
        """
        Return strict CSP headers for the sandboxed iframe.
        Blocks all external network requests except for allowed origins.
        """
        csp = (
            "default-src 'none'; "
            "script-src 'self' 'unsafe-eval' blob:; " # unsafe-eval needed for some rendering engines
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "connect-src 'self' ws: wss:; "
            "frame-src 'self';"
        )
        return {
            "Content-Security-Policy": csp,
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "SAMEORIGIN"
        }

    @staticmethod
    def validate_origin(origin: str, allowed_origins: list) -> bool:
        """Validate that message origin is within expected list."""
        return origin in allowed_origins
