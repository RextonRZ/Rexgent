"""Worker-side Socket.IO emitter.

The Celery generation worker runs in a separate process from the Socket.IO
server. A write-only RedisManager lets it publish events that the server
broadcasts to clients. All emits are best-effort — a WS failure never breaks
generation.
"""
import logging
import time
import socketio
from app.config import get_settings

logger = logging.getLogger(__name__)

_emitter: socketio.RedisManager | None = None
_last_failure = 0.0  # cooldown gate — a Redis hiccup must not mute WS forever
_COOLDOWN_SECONDS = 30


def _get_emitter() -> socketio.RedisManager:
    global _emitter
    if _emitter is None:
        # Short timeouts so a down Redis fails fast instead of blocking generation.
        _emitter = socketio.RedisManager(
            get_settings().redis_url,
            write_only=True,
            redis_options={"socket_connect_timeout": 1, "socket_timeout": 1},
        )
    return _emitter


def emit(event: str, data: dict, project_id: str) -> None:
    global _emitter, _last_failure
    if time.time() - _last_failure < _COOLDOWN_SECONDS:
        return
    try:
        _get_emitter().emit(event, data, room=f"project:{project_id}")
    except Exception as e:  # noqa: BLE001
        _last_failure = time.time()
        _emitter = None  # rebuild on next attempt — the manager may be stale
        logger.warning(
            f"WS emit paused for {_COOLDOWN_SECONDS}s — Redis unavailable: {e}"
        )
