from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.script import router as script_router

app = FastAPI(title="Rexgent", version="1.0.0", description="AI Drama Production Pipeline")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(script_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "rexgent-backend"}
