"""Socket.IO server (FastAPI side).

Uses a Redis-backed manager so events emitted from the Celery generation
worker (a separate process) are broadcast to connected browser clients.
"""
import socketio
from app.config import get_settings

settings = get_settings()

# AsyncRedisManager lets multiple processes share the same Socket.IO namespace.
mgr = socketio.AsyncRedisManager(settings.redis_url)
sio = socketio.AsyncServer(
    async_mode="asgi",
    client_manager=mgr,
    cors_allowed_origins=["http://localhost:3000"],
)


@sio.event
async def connect(sid, environ):
    pass


@sio.event
async def join_project(sid, data):
    project_id = data.get("project_id")
    if project_id:
        await sio.enter_room(sid, f"project:{project_id}")


@sio.event
async def disconnect(sid):
    pass
