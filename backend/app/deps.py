"""Shared FastAPI dependencies."""
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.auth import decode_access_token

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from a Bearer JWT, or 401.

    MUST be async: it sets the per-request Qwen key in a ContextVar, and a
    SYNC dependency runs in a threadpool whose context is discarded on return
    — so the key never reached inline endpoints (script writing, structuring)
    and every non-Celery Qwen call 402'd on a bring-your-own-key deploy. As
    an async dependency it shares the request task's context, so the key
    propagates to the endpoint and everything it awaits."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or not credentials.credentials:
        raise unauthorized

    subject = decode_access_token(credentials.credentials)
    if subject is None:
        raise unauthorized

    try:
        user_id = uuid.UUID(subject)
    except (ValueError, TypeError):
        raise unauthorized

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise unauthorized
    # bring-your-own-key: everything this request bills runs on THIS user's
    # DashScope key (the .env key only backstops when the deploy allows it)
    from app.services.api_keys import set_key_from_user
    set_key_from_user(user)
    return user
