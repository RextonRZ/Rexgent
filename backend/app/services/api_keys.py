"""Bring-your-own-key: per-user DashScope keys so a deployed instance never
bills the operator's own account.

Resolution order everywhere Qwen is called:
  1. the key of the user (or project owner) this work belongs to
  2. the server's .env key — UNLESS require_user_api_key is set, in which
     case missing means a clear 402 instead of a silent bill to the operator.

The current key travels in a ContextVar: FastAPI dependencies set it from the
authenticated user, and every Celery task sets it from the project's owner.
ContextVars propagate into asyncio.run and thread pools, so the deep call
sites (audio policy, casting, TTS) inherit it without threading a parameter
through forty signatures.
"""
import base64
import hashlib
from contextvars import ContextVar

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

_request_key: ContextVar[str | None] = ContextVar("qwen_request_key", default=None)


class MissingApiKey(RuntimeError):
    """Raised when a paid call has no usable key. The API layer maps this to
    a 402 telling the user to add their DashScope key in Settings."""

    def __init__(self):
        super().__init__(
            "No Qwen API key for this account. Paste your DashScope API key "
            "in Settings so this drama bills your own Qwen Cloud account."
        )


def _fernet() -> Fernet:
    digest = hashlib.sha256(
        ("rexgent-byok:" + get_settings().secret_key).encode()
    ).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_key(raw: str) -> str:
    return _fernet().encrypt(raw.encode()).decode()


def decrypt_key(enc: str | None) -> str | None:
    if not enc:
        return None
    try:
        return _fernet().decrypt(enc.encode()).decode()
    except (InvalidToken, ValueError):
        # secret rotated or row corrupted — treat as no key rather than crash
        return None


def set_request_key(key: str | None) -> None:
    _request_key.set(key)


def set_key_from_user(user) -> None:
    set_request_key(decrypt_key(getattr(user, "dashscope_key_enc", None)))


def use_project_key(db, project_id) -> None:
    """Celery entry point: adopt the project owner's key for this task."""
    from app.models.project import Project
    from app.models.user import User
    import uuid as _uuid

    pid = project_id if not isinstance(project_id, str) else _uuid.UUID(project_id)
    project = db.query(Project).filter(Project.id == pid).first()
    key = None
    if project is not None and project.user_id:
        try:
            owner = db.query(User).filter(User.id == _uuid.UUID(project.user_id)).first()
        except (ValueError, TypeError):
            owner = None
        if owner is not None:
            key = decrypt_key(owner.dashscope_key_enc)
    set_request_key(key)


def resolve_qwen_key(settings=None) -> str:
    """The one place a Qwen credential comes from."""
    key = _request_key.get()
    if key:
        return key
    s = settings or get_settings()
    if s.require_user_api_key:
        raise MissingApiKey()
    return s.qwen_api_key
