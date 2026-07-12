import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.graph.sync import sync_scenes
from app.models.script import Script, Scene
from app.models.shot import Shot
from app.models.character import Character
from app.schemas.shot import ShotResponse
from app.services.script_structurer import ScriptStructurer
from app.services.usage_tracker import track_project
from app.websocket.emitter import emit

from app.deps import get_current_user

router = APIRouter(prefix="/api/storyboard", tags=["storyboard"],
                   # every pipeline endpoint requires a signed-in user
                   dependencies=[Depends(get_current_user)])


def persist_scenes(db: Session, script: Script, structured: dict) -> dict:
    """Materialize Scene rows from a structured script; {number: uuid}."""
    rows: list[Scene] = []
    for sc in structured.get("scenes", []):
        scene = Scene(
            script_id=script.id,
            number=sc.get("scene_number", 0),
            title=sc.get("heading", ""),
            heading=sc.get("heading", ""),
            location=sc.get("location", ""),
            time_of_day=sc.get("time_of_day", ""),
            characters_json=sc.get("characters_present", []),
            description=sc.get("summary", ""),
            emotional_beat=sc.get("emotional_beat", ""),
            dialogue_json=sc.get("dialogue_lines", []),
            stage_directions=sc.get("stage_directions", []),
        )
        db.add(scene)
        rows.append(scene)
    if rows:
        db.flush()  # ids are assigned at flush, not construction
    return {s.number: str(s.id) for s in rows}


@router.post("/generate")
async def generate_storyboard(request: dict, db: Session = Depends(get_db)):
    project_id = request.get("project_id")
    script_id = request.get("script_id")
    target_length = int(request.get("target_length", 30))  # seconds

    if script_id:
        script = db.query(Script).filter(Script.id == uuid.UUID(script_id)).first()
    elif project_id:
        script = (
            db.query(Script)
            .filter(Script.project_id == uuid.UUID(project_id))
            .order_by(Script.created_at.desc())
            .first()
        )
    else:
        raise HTTPException(status_code=400, detail="script_id or project_id is required")

    if not script:
        raise HTTPException(status_code=404, detail="Script not found")

    pid = str(script.project_id)
    emit("stage:progress", {"stage": "storyboard", "status": "started",
         "agent": "Director", "label": "Breaking the script into shots"}, pid)

    scenes = db.query(Scene).filter(Scene.script_id == script.id).order_by(Scene.number).all()

    if not scenes and (script.raw_text or "").strip():
        emit("stage:progress", {"stage": "storyboard", "status": "update", "agent": "Director",
             "label": "The saved text reads as notes, writing the screenplay first"}, pid)
        # Self-heal: a script can exist with zero Scene rows — its first
        # structuring pass found none, or it was edited in the editor (Save
        # bumps the version but never re-parses). Structure the CURRENT text
        # and materialize the scenes before giving up.
        with track_project(script.project_id, db):
            structured = await ScriptStructurer().structure(script.raw_text)

        if not structured.get("scenes"):
            # The text isn't a screenplay at all — premise notes, character
            # intros, an outline. That's still a valid starting point: write
            # the screenplay from it, keep the user's original text as the
            # older script version.
            from app.models.project import Project
            from app.services.script_generator import ScriptGenerator

            project = (
                db.query(Project).filter(Project.id == script.project_id).first()
            )
            with track_project(script.project_id, db):
                screenplay = await ScriptGenerator().generate(
                    genre=(project.genre if project else None) or "drama",
                    premise=script.raw_text[:300],
                    notes=script.raw_text,
                    target_length=target_length,
                )
                structured = await ScriptStructurer().structure(screenplay)
            if structured.get("scenes"):
                script = Script(
                    project_id=script.project_id,
                    raw_text=screenplay,
                    structured_json=structured,
                )
                db.add(script)
                db.flush()

        scene_uuids = persist_scenes(db, script, structured)
        if scene_uuids:
            script.structured_json = structured
            db.commit()
            sync_scenes(str(script.project_id), structured, scene_uuids=scene_uuids)
            scenes = (
                db.query(Scene)
                .filter(Scene.script_id == script.id)
                .order_by(Scene.number)
                .all()
            )

    if not scenes:
        emit("stage:progress", {"stage": "storyboard", "status": "failed", "agent": "Director",
             "label": "No scenes found in the script"}, pid)
        raise HTTPException(
            status_code=400,
            detail="No scenes found in the script. Rewrite it with clear scene headings (INT./EXT. or Scene 1, Scene 2...), then try again.",
        )

    characters = db.query(Character).filter(Character.project_id == script.project_id).all()
    # ── stage order is real, not decorative: the Director stages shots AROUND
    # the cast (who is in frame, what they look like). Storyboarding before
    # casting produces shots with unknown names that generation then rejects.
    if not characters:
        emit("stage:progress", {"stage": "storyboard", "status": "failed", "agent": "Director",
             "label": "Cast the characters first"}, pid)
        raise HTTPException(
            status_code=400,
            detail="Cast the characters first: the Director stages every shot around them. Open the Characters page and extract the cast, then storyboard.",
        )
    # Boarding runs in the BACKGROUND: a multi-scene board takes minutes of
    # per-scene staging, set dressing and location plates — far too long for
    # one HTTP request. A browser hiccup used to CANCEL the request
    # server-side and kill the board mid-scene with zero shots saved. The op
    # narrates itself over stage:progress and tool events; the storyboard
    # page refreshes when the completed event lands.
    from app.workers.storyboard_worker import run_storyboard_job
    run_storyboard_job.delay(str(script.id), target_length)
    return {"status": "started", "scenes": len(scenes)}


@router.get("/project/{project_id}")
async def list_shots(project_id: str, db: Session = Depends(get_db)):
    script = (
        db.query(Script)
        .filter(Script.project_id == uuid.UUID(project_id))
        .order_by(Script.created_at.desc())
        .first()
    )
    if not script:
        return {"scenes": []}

    scenes = db.query(Scene).filter(Scene.script_id == script.id).order_by(Scene.number).all()
    # which episode each scene belongs to (the structurer records it; a
    # script from before episodes, or a one-episode drama, is all episode 1)
    ep_by_scene: dict = {}
    for sc in (script.structured_json or {}).get("scenes") or []:
        if sc.get("scene_number") is not None:
            try:
                ep_by_scene[int(sc["scene_number"])] = int(sc.get("episode_number") or 1)
            except (TypeError, ValueError):
                pass
    result = []
    for scene in scenes:
        shots = db.query(Shot).filter(Shot.scene_id == scene.id).order_by(Shot.number).all()
        set_json = getattr(scene, "set_json", None) or {}
        result.append({
            "id": str(scene.id),
            "scene_number": scene.number,
            "episode": ep_by_scene.get(scene.number, 1),
            "heading": scene.heading,
            "set_items": set_json.get("set_items") or [],
            "state_changes": set_json.get("state_changes") or [],
            "shots": [ShotResponse.model_validate(s).model_dump() for s in shots],
        })
    return {"scenes": result}


@router.delete("/scene/{scene_id}")
async def delete_scene(scene_id: str, db: Session = Depends(get_db)):
    """Remove a scene and everything that hangs off it: its shots (FK
    cascade) and its synthesized voice lines (matched by scene_number, so a
    deleted scene's dialogue can never be placed onto the cut). Remaining
    scene numbers keep their gaps on purpose — renumbering would detach every
    later scene from its already-synthesized lines."""
    scene = db.query(Scene).filter(Scene.id == uuid.UUID(scene_id)).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    script = db.query(Script).filter(Script.id == scene.script_id).first()
    from app.models.line_audio import LineAudio
    n_lines = 0
    if script:
        n_lines = (db.query(LineAudio)
                   .filter(LineAudio.project_id == script.project_id,
                           LineAudio.scene_number == scene.number)
                   .delete())
    number = scene.number
    db.delete(scene)
    db.commit()
    return {"deleted": True, "scene_number": number, "voice_lines_removed": n_lines}


@router.patch("/{shot_id}", response_model=ShotResponse)
async def update_shot(shot_id: str, updates: dict, db: Session = Depends(get_db)):
    shot = db.query(Shot).filter(Shot.id == uuid.UUID(shot_id)).first()
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")
    allowed = {
        "shot_type", "camera_movement", "lighting", "colour_mood", "action",
        "dialogue", "emotional_beat", "estimated_duration_seconds",
        "characters_in_frame", "notes", "director_note", "quality_tier",
    }
    for key, value in updates.items():
        if key in allowed:
            setattr(shot, key, value)
    db.commit()
    db.refresh(shot)
    return shot


@router.delete("/{shot_id}")
async def delete_shot(shot_id: str, db: Session = Depends(get_db)):
    shot = db.query(Shot).filter(Shot.id == uuid.UUID(shot_id)).first()
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")
    db.delete(shot)
    db.commit()
    return {"deleted": shot_id}
