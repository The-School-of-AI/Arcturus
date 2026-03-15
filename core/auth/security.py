import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Any
import jwt
from passlib.context import CryptContext

# Secret key for JWT signing (HS256). No fallback - must be set for login/register.
# When unset, app still starts; guest flow works; login/register return 503.
SECRET_KEY = os.environ.get("MNEMO_SECRET_KEY") or ""
ALGORITHM = "HS256"

AUTH_NOT_CONFIGURED_MSG = (
    "JWT signing is not configured. Generate an HS256 secret and set MNEMO_SECRET_KEY "
    "in your environment. Example: openssl rand -base64 48"
)


def is_jwt_configured() -> bool:
    """Returns True if MNEMO_SECRET_KEY is set (required for login/register)."""
    return bool(SECRET_KEY)
# Using 30-day token as specified in Phase 5 Auth Design docs
ACCESS_TOKEN_EXPIRE_DAYS = 30

# Password hashing context (bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against the stored hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Creates a bcrypt hash of the password."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JWT access token. Raises ValueError if MNEMO_SECRET_KEY is not set."""
    if not is_jwt_configured():
        raise ValueError(AUTH_NOT_CONFIGURED_MSG)
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
        
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    """Decodes a JWT access token. Returns None if invalid, expired, or JWT not configured."""
    if not is_jwt_configured():
        return None
    try:
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return decoded_token
    except jwt.PyJWTError:
        return None
