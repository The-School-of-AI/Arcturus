from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import uuid

from core.auth.security import decode_access_token
from core.auth.context import set_current_user_id, set_current_request_guest

import os

def is_auth_enabled() -> bool:
    """Check if Phase 5 Auth mechanism (JWT/Header context) is enabled."""
    return os.environ.get("AUTH_ENABLED", "true").lower() == "true"

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 0. Skip auth injection if entirely disabled
        if not is_auth_enabled():
            return await call_next(request)

        # We must explicitly define public vs protected routes 
        # (For now we rely on the route handlers or global config. 
        #  If we want to enforce here, we could check the path).
        # Per design doc: all Mnemo data routes (/runs, /remme, /api/sync) are protected.

        user_id = None
        is_guest = False

        # 1. Try JWT from Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            payload = decode_access_token(token)
            if payload and "sub" in payload:
                user_id = str(payload["sub"])
                is_guest = False

        # 2. If no valid JWT, fallback to X-User-Id header (Guest)
        if not user_id:
            guest_id = request.headers.get("X-User-Id")
            if guest_id:
                # Strip prefix if present
                clean_guest_id = guest_id.replace("guest_", "") if guest_id.startswith("guest_") else guest_id
                try:
                    # Validate it's a valid UUID
                    val = uuid.UUID(clean_guest_id)
                    user_id = str(val)
                    is_guest = True
                except ValueError:
                    pass
        
        # 3. If this is a protected route and we still have no identity, reject it early.
        # Check path strictly, supporting both /path and /api/path mappings
        path = request.url.path
        if path.startswith("/runs") or path.startswith("/remme") or path.startswith("/api/sync") \
           or path.startswith("/api/runs") or path.startswith("/api/remme"):
            if not user_id:
                return JSONResponse(
                    status_code=401, 
                    content={"detail": "Missing or invalid authentication (JWT or X-User-Id required)"}
                )
                
        # Inject the identity and guest flag into running context
        set_current_user_id(user_id)
        set_current_request_guest(is_guest)
        
        # Proceed with request
        response = await call_next(request)
        
        # Cleanup context (though contextvars handles it per-async-task anyway)
        set_current_user_id(None)
        set_current_request_guest(False)
        
        return response
