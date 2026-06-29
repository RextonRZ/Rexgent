"""Authentication primitives: password hashing (bcrypt) and JWT sessions.

Users live in PostgreSQL (Alibaba Cloud RDS in production). Sessions are
stateless JWTs signed with settings.secret_key. No third-party identity
provider — this is self-contained, portable auth that runs anywhere the
backend runs.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import get_settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7


def hash_password(password: str) -> str:
    """Return a bcrypt hash of the password (utf-8, salted)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time check of a plaintext password against a stored hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, expires_days: int = ACCESS_TOKEN_EXPIRE_DAYS) -> str:
    """Sign a JWT whose `sub` claim is the user id."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "iat": now,
        "exp": now + timedelta(days=expires_days),
    }
    return jwt.encode(payload, get_settings().secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Return the subject (user id) if the token is valid and unexpired, else None."""
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None
