import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.project import Project
from app.agent.graph import build_pipeline_graph

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/auto")
async def run_auto(request: dict, db: Session = Depends(get_db)):
    """Autonomous full-pipeline run from a premise.

    The agent generates + judges (with a revise loop) + extracts characters +
    storyboards + allocates budget, then dispatches async video generation and
    returns a report. Video progress streams over the existing WebSocket.
    """
    project_id = request.get("project_id")
    premise = request.get("premise", "")
    genre = request.get("genre", "drama")
    tone = request.get("tone", "dramatic")
    language = request.get("language", "en")
    target_length = int(request.get("target_length", 5))
    episode_count = int(request.get("episode_count", 1))
    # Plan-only unless the caller explicitly opts into spending the voucher.
    dispatch_video = bool(request.get("dispatch_video", False))

    if not project_id:
        raise HTTPException(status_code=400, detail="project_id required")
    if not db.query(Project).filter(Project.id == uuid.UUID(project_id)).first():
        raise HTTPException(status_code=404, detail="Project not found")
    if not premise:
        raise HTTPException(status_code=400, detail="premise required")

    graph = build_pipeline_graph(db=db)
    try:
        final_state = await graph.ainvoke({
            "project_id": project_id, "premise": premise, "genre": genre,
            "tone": tone, "language": language, "auto": True, "revise_count": 0,
            "target_length": target_length, "episode_count": episode_count,
            "dispatch_video": dispatch_video,
        })
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if "invalid_api_key" in msg or "401" in msg:
            raise HTTPException(
                status_code=502,
                detail="Qwen API key rejected. Check QWEN_API_KEY and QWEN_BASE_URL "
                       "(international keys need the dashscope-intl endpoint).",
            )
        raise HTTPException(status_code=502, detail=f"Agent run failed: {msg}")

    return {
        "status": "complete",
        "script_id": final_state.get("script_id"),
        "judgement": final_state.get("judgement"),
        "characters": len(final_state.get("characters", [])),
        "shots": len(final_state.get("shots", [])),
        "budget": final_state.get("budget"),
        "job_id": final_state.get("job_id"),
        "dispatched": bool(final_state.get("job_id")),
        "revisions": final_state.get("revise_count", 0),
        "report": final_state.get("report"),
    }
