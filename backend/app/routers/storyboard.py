import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.graph.sync import sync_scenes
from app.models.script import Script, Scene
from app.models.shot import Shot
from app.models.character import Character
from app.schemas.shot import ShotResponse
from app.services.render_plan import predict_scene_plan
from app.services.script_structurer import ScriptStructurer
from app.services.usage_tracker import track_project
from app.websocket.emitter import emit
from app.config import get_settings

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
    requested_length = request.get("target_length")  # seconds, optional

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
    # Honor the scope picked at creation when the caller doesn't specify one:
    # the manual Generate storyboard button sends nothing, and a 1-episode
    # 10-second drama used to silently board at the 30-second default. The
    # stored target is seconds PER EPISODE; boarding budgets the whole drama.
    if requested_length is not None:
        target_length = int(requested_length)
    else:
        from app.models.project import Project
        proj = db.query(Project).filter(Project.id == script.project_id).first()
        per_episode = int(getattr(proj, "target_length", None) or 30)
        episodes = max(1, int(getattr(proj, "episode_count", None) or 1))
        target_length = per_episode * episodes

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
            # the script's own prose decides the language — a zh screenplay
            # must not self-heal through an en-mode structuring pass
            from app.services.language import detect_language
            structured = await ScriptStructurer().structure(
                script.raw_text, language=detect_language(script.raw_text))

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
                structured = await ScriptStructurer().structure(
                    screenplay, language=detect_language(screenplay))
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


def build_bible(db: Session, project_id) -> dict:
    """The same character/location bible generation renders against, built
    straight from this project's rows — so a storyboard shot's render_plan
    can never drift from what the runner will actually see. Mirrors
    GenerationRunner._load_bible; imported lazily to avoid pulling the
    renderer's heavy clients into every storyboard request."""
    from app.models.location_plate import LocationPlate
    from app.models.style_preset import StylePreset
    from app.services.generation_runner import GenerationRunner
    characters = db.query(Character).filter(Character.project_id == project_id).all()
    locations = db.query(LocationPlate).filter(LocationPlate.project_id == project_id).all()
    style = db.query(StylePreset).filter(StylePreset.project_id == project_id).first()
    return GenerationRunner._shape_bible(characters, locations, style.plate_image_url if style else None)


def shots_with_render_plan(shots: list[Shot], bible: dict) -> list[dict]:
    """Serialize a scene's ordered shots and attach each one's render_plan —
    the {model, lipsync} it will actually render on under LIVE settings —
    so the frontend can show the model a shot really renders on instead of a
    label that can drift from runtime routing. `shots` must be the scene's
    shots in generation order; predict_scene_plan returns one entry per
    input shot, in the same order, so they zip 1:1."""
    settings = get_settings()
    plans = predict_scene_plan(
        shots, bible,
        identity_routing_v2=settings.identity_routing_v2,
        anchor_ref_model=settings.anchor_ref_model,
        lipsync_enabled=settings.lipsync_enabled,
        happyhorse_native_talk=settings.happyhorse_native_talk,
        route_continuation_to_happyhorse=settings.route_continuation_to_happyhorse,
        wan_primary=settings.wan_primary,
    )
    out = []
    for shot, plan in zip(shots, plans):
        data = ShotResponse.model_validate(shot).model_dump()
        data["render_plan"] = plan
        out.append(data)
    return out


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
    bible = build_bible(db, script.project_id)
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
            "shots": shots_with_render_plan(shots, bible),
        })
    return {"scenes": result}


@router.delete("/scene/{scene_id}")
async def delete_scene(scene_id: str, db: Session = Depends(get_db)):
    """Remove a scene and its shots (FK cascade). Remaining scene numbers keep
    their gaps on purpose: renumbering would detach every later scene from the
    rest of the storyboard."""
    scene = db.query(Scene).filter(Scene.id == uuid.UUID(scene_id)).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    number = scene.number
    db.delete(scene)
    db.commit()
    return {"deleted": True, "scene_number": number}


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
