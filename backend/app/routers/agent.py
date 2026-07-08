import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.project import Project
from app.agent.graph import build_pipeline_graph
from app.agents.registry import AGENTS
from app.models.agent_report import AgentReport
from app.models.character import Character

from app.deps import get_current_user

router = APIRouter(prefix="/api/agent", tags=["agent"],
                   # every pipeline endpoint requires a signed-in user
                   dependencies=[Depends(get_current_user)])


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
    model = request.get("model", "")
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
            "tone": tone, "model": model, "language": language,
            "auto": True, "revise_count": 0,
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
    # Continue the pipeline: storyboard, then fit the budget — the resumed
    # plan lands in the same reviewed state a non-paused run reaches.
    script = (db.query(Script).filter(Script.project_id == uuid.UUID(project_id))
              .order_by(Script.created_at.desc()).first())
    if script:
        from app.agent.pipeline_ops import allocate_budget_op
        shots = await generate_storyboard_op(db, str(script.id))
        if shots:
            allocate_budget_op(db, project_id, shots)
    return {"resumed": True}


@router.post("/{project_id}/chat")
async def chat_with_showrunner(project_id: str, body: dict, db: Session = Depends(get_db)):
    """Ask the showrunner about THIS drama. Answers are grounded in a compact
    context pack (script digest, cast, spend, recent agent decisions) on the
    mid tier model, and persisted as an agent report so the conversation
    survives a reload."""
    import json as _json
    question = (body.get("question") or "").strip()[:500]
    if not question:
        raise HTTPException(status_code=400, detail="question required")
    project = db.query(Project).filter(Project.id == uuid.UUID(project_id)).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    from app.models.script import Script
    from app.services.context_compressor import script_digest
    from app.services.cost_ledger import aggregate
    from app.services.qwen_client import QwenClient
    from app.services.usage_tracker import track_project
    from app.config import get_settings

    script = (db.query(Script).filter(Script.project_id == project.id)
              .order_by(Script.created_at.desc()).first())
    chars = db.query(Character).filter(Character.project_id == project.id).all()
    reports = (db.query(AgentReport).filter(AgentReport.project_id == project.id)
               .order_by(AgentReport.created_at.desc()).limit(10).all())
    agg = aggregate(db, project_id)
    # WHERE the production actually stands — without this the model only sees
    # the script digest + the judge's old critique and answers every "what's
    # next" with "refine the ending", even when the script stage is long done.
    from app.services.pipeline_progress import STAGE_PAGES, next_stage, stage_progress
    progress = stage_progress(db, project.id)
    upcoming = next_stage(progress)
    context = {
        "title": project.title, "genre": project.genre, "premise": project.premise,
        "format": getattr(project, "video_ratio", "9:16"),
        "spend_cap_usd": project.credit_budget,
        "pipeline_progress": progress,
        "next_incomplete_stage": (
            {"stage": upcoming, "page": STAGE_PAGES[upcoming]} if upcoming
            else "all stages complete, the episode is exported"),
        "script": script_digest(script.structured_json) if script and script.structured_json else {},
        "cast": [{"name": c.name, "role": c.role} for c in chars],
        "spend": {"total_usd": agg.get("grand_total"),
                  "by_category": agg.get("by_category"),
                  "llm_tokens": (agg.get("llm") or {}).get("total_tokens")},
        "recent_agent_decisions": [
            {"agent": r.agent, "stage": r.stage, "note": r.rationale}
            for r in reversed(reports)
        ],
    }
    system = (
        "You are the Showrunner of this AI short drama production. Answer the "
        "user's question about THIS production only, grounded strictly in the "
        "context given. Be concrete and brief: two to four plain sentences, no "
        "markdown, no lists. When asked what to do next, answer from "
        "pipeline_progress and next_incomplete_stage: stages marked true are "
        "DONE, never suggest redoing or polishing them unless the user asks; "
        "point to the next incomplete stage and its page. Old agent critique "
        "notes describe past decisions, not open tasks. If the context does "
        "not contain the answer, say so and suggest which page of the studio "
        "would."
    )
    qwen = QwenClient(get_settings())
    with track_project(project_id, db):
        answer = await qwen.chat(
            [{"role": "system", "content": system},
             {"role": "user",
              "content": f"Production context:\n{_json.dumps(context, ensure_ascii=False)}\n\nQuestion: {question}"}],
            task="chat", temperature=0.4, max_tokens=400,
        )
    from app.agents.reporter import report_agent
    report_agent(db, project_id, agent="Showrunner", stage="chat",
                 decision={"question": question}, rationale=answer, confidence=1.0)
    return {"answer": answer}


@router.patch("/{project_id}/auto-clarify")
def set_auto_clarify(project_id: str, enabled: bool, db: Session = Depends(get_db)):
    p = db.query(Project).filter(Project.id == uuid.UUID(project_id)).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    p.auto_clarify = enabled
    db.commit()
    return {"auto_clarify": enabled}
