from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routers.projects import router as projects_router
from app.routers.script import router as script_router
from app.routers.character import router as character_router
from app.routers.graph import router as graph_router
from app.routers.storyboard import router as storyboard_router
from app.routers.budget import router as budget_router
from app.routers.generation import router as generation_router
from app.routers.edit import router as edit_router
from app.routers.export import router as export_router
from app.routers.agent import router as agent_router
from app.routers.auth import router as auth_router
from app.routers.casting import router as casting_router

app = FastAPI(title="Rexgent", version="1.0.0", description="AI Drama Production Pipeline")

# localhost for dev; FRONTEND_ORIGIN (env) adds the deployed site.
_origins = ["http://localhost:3000"]
if get_settings().frontend_origin:
    _origins.append(get_settings().frontend_origin.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(script_router)
app.include_router(character_router)
app.include_router(graph_router)
app.include_router(storyboard_router)
app.include_router(budget_router)
app.include_router(generation_router)
app.include_router(edit_router)
app.include_router(export_router)
app.include_router(agent_router)
app.include_router(casting_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "rexgent-backend"}


# Socket.IO ASGI wrapper. Serve with: uvicorn app.main:socket_app
import socketio  # noqa: E402
from app.websocket.ws_manager import sio  # noqa: E402

socket_app = socketio.ASGIApp(sio, other_asgi_app=app)
