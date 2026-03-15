from contextvars import ContextVar
from typing import Optional

# This context variable will hold the user_id (as a string) for the current request context.
# It defaults to None if not set.
request_user_id: ContextVar[Optional[str]] = ContextVar("request_user_id", default=None)
# True when identity came from X-User-Id (guest), False when from JWT. Used e.g. to enforce guest-only local_only spaces.
request_is_guest: ContextVar[bool] = ContextVar("request_is_guest", default=False)

def set_current_user_id(user_id: Optional[str]) -> None:
    """Set the user_id for the current request context."""
    request_user_id.set(user_id)

def get_current_user_id() -> Optional[str]:
    """Get the user_id from the current request context."""
    return request_user_id.get()

def set_current_request_guest(is_guest: bool) -> None:
    """Set whether the current request identity is a guest (X-User-Id) vs registered (JWT)."""
    request_is_guest.set(is_guest)

def get_is_guest() -> bool:
    """Return True if the current request is authenticated as a guest (no JWT)."""
    return request_is_guest.get() or False
