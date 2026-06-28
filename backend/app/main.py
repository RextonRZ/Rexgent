from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.script import router as script_router
from app.routers.character import router as character_router
from app.routers.graph import router as graph_router
from app.routers.storyboard import router as storyboard_router
from app.routers.budget import router as budget_router

app = FastAPI(title="Rexgent", version="1.0.0", description="AI Drama Production Pipeline")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(script_router)
app.include_router(character_router)
app.include_router(graph_router)
app.include_router(storyboard_router)
app.include_router(budget_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "rexgent-backend"}
