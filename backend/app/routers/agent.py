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
        # without Full Auto the graph ends at the script checkpoint — the
        # Showrunner chat's cards drive each later stage from there
        "status": "complete" if dispatch_video else "script_ready",
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


@router.get("/{project_id}/tools")
def tool_snapshot(project_id: str):
    """Latest state per (stage, tool) — the crew graph hydrates from this on
    load, so finished green ticks survive refresh and dock re-opens."""
    from app.websocket.tool_events import load_tool_snapshot
    return {"tools": load_tool_snapshot(project_id)}


# What the crew graph shows, in TRUE execution order — the chat's manual for
# "what is this node / why is it idle". Mirrors frontend/lib/stageTools.ts:
# auto nodes fire by themselves every run; conditional nodes fire by themselves
# only when their condition holds; on-demand nodes fire only from a user action
# and never block the stage.
CREW_PIPELINE_GUIDE = {
    "script": {"agent": "Screenwriter", "steps": [
        "llm_write (auto: drafts the screenplay)",
        "structure_scenes (auto: splits the draft into scenes)",
        "write_script_db (auto: saves the scenes)",
        "narrative_judge (conditional: Full Auto judges every draft automatically; on the Script page it runs when the user presses Score Quality)",
        "plot_gap_check (on-demand: the Run AI Analysis button on the Script page, scans for plot holes and pacing problems)",
        "ending_engine (on-demand: runs with Run AI Analysis, grades the ending and pitches alternates)",
    ]},
    "characters": {"agent": "Casting Director", "steps": [
        "extract_cast (auto: reads the cast from the script)",
        "write_cast_db (auto: saves the cast)",
        "map_relationships (conditional: builds itself right after extraction and heals on page load if bonds are missing, no button needed)",
        "profile_cast (conditional: runs by itself inside Generate Plates for any character still missing a visual look, so skipping face upload never blocks anything; the Generate Appearance (no photo) button on a character card re-runs it for one character)",
        "generate_plates (auto: renders style, location and character plates)",
        "face_lock (conditional: locks automatically when plates capture a clear face; uploading a reference photo on a character card locks a real look instead. Uploading a face is ALWAYS optional, never required)",
    ]},
    "storyboard": {"agent": "Director", "steps": [
        "memory_recall (auto: reads facts earlier scenes established, from the narrative memory graph)",
        "shot_breakdown (auto: stages each scene into shots)",
        "set_design (auto: pins props and set state per scene)",
        "write_shots_db (auto: saves the shots)",
    ]},
    "generate": {"agent": "Showrunner", "steps": [
        "budget_allocate (conditional: fits itself on the Storyboard page the moment the board lands, splitting the cap across shots and picking tiers; it appears in the crew graph only when it actually runs)",
        "prompt_craft (auto, per shot: expands the beat into concrete physical action, aims a negative prompt at the wrong default interpretation, and asks the Neo4j world graph whether an active event overrides the location's usual crowd behavior)",
        "dispatch_video (auto, per shot: renders the clip)",
        "verify_face (auto, per shot: continuity scoring of face, outfit, background)",
        "write_clip_db (auto, per shot: saves the clip)",
        "self_correct (conditional: only when a render fails and the crew retries it, idle means nothing broke)",
        "fix_take (on-demand: Fix take on a flagged clip in the Edit room)",
    ]},
    "export": {"agent": "Editor", "steps": [
        "stitch_clips (auto: joins the approved clips into one cut)",
        "burn_captions (conditional: when the cut has dialogue to caption)",
        "mix_audio (conditional: when there are voices or music to mix)",
        "render_mp4 (auto: uploads the final cut)",
        "write_export_db (auto: records the export)",
    ]},
    "stage_order_rules": (
        "Stages run in order: script, then characters, then storyboard, then "
        "generate, then export. Manual mode enforces it: casting needs a "
        "script, storyboarding needs a cast, generation needs storyboard shots "
        "and every character to have a look. A look is auto-written by "
        "Generate Plates or taken from an uploaded face photo, and uploading "
        "a face is always optional."
    ),
}


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
    from app.services.pipeline_progress import (STAGE_PAGES, next_stage,
                                                 next_step_card, stage_progress,
                                                 stale_stages)
    progress = stage_progress(db, project.id)
    upcoming = next_stage(progress)
    stale = [s for s, flag in stale_stages(db, project.id).items() if flag]
    # CURRENT blockers, computed live — so "what's this error" gets a real
    # answer instead of generic script advice
    blockers: list = []
    try:
        from app.services.guardrails import PreGenerationValidator
        from app.models.shot import Shot
        from app.models.script import Scene as _Scene
        chars_all = db.query(Character).filter(Character.project_id == project.id).all()
        script_row = (db.query(Script).filter(Script.project_id == project.id)
                      .order_by(Script.created_at.desc()).first())
        shots_all = []
        if script_row:
            scene_ids = [s.id for s in db.query(_Scene.id)
                         .filter(_Scene.script_id == script_row.id).all()]
            if scene_ids:
                shots_all = db.query(Shot).filter(Shot.scene_id.in_(scene_ids)).all()
        if shots_all:
            preflight = PreGenerationValidator().validate(
                characters=[{"name": c.name,
                             "video_prompt_fragment": c.video_prompt_fragment,
                             "visual_description": c.visual_description}
                            for c in chars_all],
                shots=[{"characters_in_frame": s.characters_in_frame,
                        "estimated_duration_seconds": s.estimated_duration_seconds}
                       for s in shots_all])
            if not preflight.get("pass"):
                blockers = (preflight.get("issues") or []) +                            (preflight.get("missing_visuals") or [])
    except Exception:  # noqa: BLE001
        pass
    # what each crew node actually is + what has ACTUALLY run this production,
    # so "why is self_correct idle" gets the real answer (conditional, healthy)
    # instead of an invented problem
    tool_status: dict = {}
    try:
        from app.websocket.tool_events import load_tool_snapshot
        tool_status = {stage: {tool: ev.get("status") for tool, ev in tools.items()}
                       for stage, tools in load_tool_snapshot(project_id).items()}
    except Exception:  # noqa: BLE001
        pass
    context = {
        "title": project.title, "genre": project.genre, "premise": project.premise,
        "format": getattr(project, "video_ratio", "9:16"),
        "spend_cap_usd": project.credit_budget,
        "pipeline_progress": progress,
        "stale_stages": stale,
        "generation_blockers": blockers,
        "crew_pipeline": CREW_PIPELINE_GUIDE,
        "tool_status": tool_status,
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
        "markdown, no lists. Answer ONLY what the user asked; do NOT tack on a "
        "suggestion to move to the next stage unless the user explicitly asks "
        "what to do next. When asked what to do next, answer from "
        "pipeline_progress and next_incomplete_stage: stages marked true are "
        "DONE, never suggest redoing or polishing them unless the user asks; "
        "point to the next incomplete stage and its page. Old agent critique "
        "notes describe past decisions, not open tasks. If generation_blockers "
        "is non-empty and the user asks about an error or being blocked, "
        "explain the blocker plainly and give the fix: missing visual "
        "descriptions are fixed on the Characters page by clicking Generate "
        "Plates (a look is auto-written) or uploading a face photo. When asked "
        "about a node in the crew graph or why a step is idle or not running, "
        "answer from crew_pipeline and tool_status: conditional and on-demand "
        "steps are healthy when idle, so say exactly what triggers them "
        "instead of treating idle as a problem, and never tell the user a "
        "face upload is required. If stale_stages is non-empty, the user went "
        "back and redid an earlier stage, so those later stages still reflect "
        "the OLD version: when asked what to do next, say they should be "
        "re-run, in pipeline order. If the context does not contain the "
        "answer, say so and suggest which page of the studio would."
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
    # The go-there button ONLY rides along when the user actually asks what to do
    # next — otherwise every answer (about a shot, a cost, an error) sprouted a
    # "storyboard the scene" nudge the user never asked for.
    import re as _re
    _asks_next = _re.search(
        r"\bnext\b|what.*\b(do|now)\b|proceed|continue|then what|move on|move forward|"
        r"接下来|下一步|然后|现在.*(做|干)|该做|怎么办|下一个",
        question, _re.IGNORECASE)
    return {"answer": answer,
            "next_step": next_step_card(progress) if _asks_next else None}


@router.patch("/{project_id}/auto-clarify")
def set_auto_clarify(project_id: str, enabled: bool, db: Session = Depends(get_db)):
    p = db.query(Project).filter(Project.id == uuid.UUID(project_id)).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    p.auto_clarify = enabled
    db.commit()
    return {"auto_clarify": enabled}
