"""Bring-your-own-key: encryption round-trips, resolution order, and the
require flag refusing paid work without a personal key."""
import pytest

from app.services.api_keys import (
    MissingApiKey,
    decrypt_key,
    encrypt_key,
    resolve_qwen_key,
    set_request_key,
)
from app.config import get_settings


@pytest.fixture(autouse=True)
def _clean_context():
    set_request_key(None)
    yield
    set_request_key(None)


def test_encrypt_round_trip():
    enc = encrypt_key("sk-user-abc123456")
    assert enc != "sk-user-abc123456"
    assert decrypt_key(enc) == "sk-user-abc123456"


def test_decrypt_garbage_is_none_not_crash():
    assert decrypt_key(None) is None
    assert decrypt_key("") is None
    assert decrypt_key("not-a-fernet-token") is None


def test_user_key_wins_over_env():
    set_request_key("sk-from-user")
    assert resolve_qwen_key() == "sk-from-user"


def test_falls_back_to_env_key():
    s = get_settings()
    assert resolve_qwen_key(s) == s.qwen_api_key


def test_require_flag_refuses_without_user_key():
    s = get_settings().model_copy(update={"require_user_api_key": True})
    with pytest.raises(MissingApiKey):
        resolve_qwen_key(s)


def test_require_flag_satisfied_by_user_key():
    s = get_settings().model_copy(update={"require_user_api_key": True})
    set_request_key("sk-from-user")
    assert resolve_qwen_key(s) == "sk-from-user"


def test_qwen_client_uses_request_key():
    from app.services.qwen_client import QwenClient
    set_request_key("sk-context-key")
    client = QwenClient(get_settings())
    assert client.api_key == "sk-context-key"


def test_get_current_user_is_async_so_the_key_propagates():
    """A SYNC dependency runs in a threadpool whose context is discarded, so
    the per-request key never reached inline endpoints. get_current_user must
    stay async for BYOK to work outside the Celery workers."""
    import inspect
    from app.deps import get_current_user
    assert inspect.iscoroutinefunction(get_current_user)


def test_async_dependency_contextvar_reaches_endpoint():
    """Prove the fix at the framework level: a ContextVar set inside an ASYNC
    FastAPI dependency is visible in the endpoint (shared request context),
    which a sync/threadpool dependency would not guarantee."""
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient
    from app.services.api_keys import set_request_key, resolve_qwen_key
    from app.config import get_settings

    async def dep():
        set_request_key("sk-context-propagated")

    app = FastAPI()

    @app.get("/probe", dependencies=[Depends(dep)])
    def probe():
        return {"key": resolve_qwen_key(get_settings())}

    set_request_key(None)
    r = TestClient(app).get("/probe")
    assert r.json()["key"] == "sk-context-propagated"
