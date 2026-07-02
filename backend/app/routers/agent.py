import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.project import Project
from app.agent.graph import build_pipeline_graph
from app.agents.registry import AGENTS
from app.models.agent_report import AgentReport
from app.models.character import Character

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
    target_length = int(request.get("target_length", 30))  # seconds
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


@router.get("/registry")
def registry():
    return AGENTS


@router.get("/reports/{project_id}")
def reports(project_id: str, db: Session = Depends(get_db)):
    rows = (db.query(AgentReport).filter(AgentReport.project_id == uuid.UUID(project_id))
            .order_by(AgentReport.created_at).all())
    return [{"agent": r.agent, "stage": r.stage, "decision": r.decision,
             "rationale": r.rationale, "confidence": r.confidence,
             "created_at": r.created_at.isoformat() if r.created_at else None} for r in rows]


@router.get("/clarifications/{project_id}")
def clarifications(project_id: str, db: Session = Depends(get_db)):
    row = (db.query(AgentReport).filter(AgentReport.project_id == uuid.UUID(project_id),
           AgentReport.agent == "clarification").order_by(AgentReport.created_at.desc()).first())
    return (row.decision or {"ambiguities": []}) if row else {"ambiguities": []}


@router.post("/clarifications/{project_id}/answer")
async def answer(project_id: str, body: dict, db: Session = Depends(get_db)):
    from app.models.script import Script
    from app.agent.pipeline_ops import generate_storyboard_op
    from app.websocket.emitter import emit
    if not db.query(Project).filter(Project.id == uuid.UUID(project_id)).first():
        raise HTTPException(status_code=404, detail="Project not found")
    # Apply each answer as an appended note on any character whose name matches the topic.
    for ans in body.get("answers", []):
        topic, text = ans.get("topic", ""), ans.get("answer", "")
        chars = db.query(Character).filter(Character.project_id == uuid.UUID(project_id)).all()
        for c in chars:
            if topic and topic.lower() in (c.name or "").lower():
                c.physical_description = f"{c.physical_description or ''}. {text}".strip(". ")
                c.visual_description = f"{c.visual_description or ''}. {text}".strip(". ")
    db.commit()
    emit("clarification.resolved", {}, project_id)
    # Continue the pipeline: run the storyboard now that ambiguity is resolved.
    script = (db.query(Script).filter(Script.project_id == uuid.UUID(project_id))
              .order_by(Script.created_at.desc()).first())
    if script:
        await generate_storyboard_op(db, str(script.id))
    return {"resumed": True}


@router.patch("/{project_id}/auto-clarify")
def set_auto_clarify(project_id: str, enabled: bool, db: Session = Depends(get_db)):
    p = db.query(Project).filter(Project.id == uuid.UUID(project_id)).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    p.auto_clarify = enabled
    db.commit()
    return {"auto_clarify": enabled}
