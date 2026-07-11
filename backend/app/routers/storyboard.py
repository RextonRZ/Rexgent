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
from app.services.storyboard_generator import StoryboardGenerator, plan_shot_budget
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
    char_map = {
        c.name.upper(): {
            "name": c.name,
            "role": c.role,
            "visual_description": c.visual_description or "",
        }
        for c in characters
    }

    # Replace existing shots for these scenes (re-generation).
    scene_ids = [s.id for s in scenes]
    db.query(Shot).filter(Shot.scene_id.in_(scene_ids)).delete(synchronize_session=False)

    shots_per_scene, shot_seconds = plan_shot_budget(len(scenes), target_length)
    generator = StoryboardGenerator()
    all_shots = []
    dressed = 0
    # full parity with the full-auto path: the same narrative-memory loop and
    # the same crew-graph tool events, so the manual button is not a lesser
    # Director (memory_recall / shot_breakdown / set_design nodes all light)
    from app.graph.sync import recall_facts_before_scene, sync_scene_facts
    from app.websocket.tool_events import tool_event, tool_run

    for scene_index, scene in enumerate(scenes, start=1):
        emit("stage:progress", {"stage": "storyboard", "status": "update", "agent": "Director",
             "label": f"Scene {scene.number}: staging shots and set dressing",
             "index": scene_index, "total": len(scenes)}, pid)
        scene_chars = [
            char_map.get(str(name).upper(), {"name": name})
            for name in (scene.characters_json or [])
        ]
        # ── narrative memory READ: what earlier scenes established (Neo4j) ──
        tool_event(pid, "storyboard", "memory_recall", "started",
                   agent="Director", index=scene_index, total=len(scenes))
        established = recall_facts_before_scene(pid, scene.number)
        tool_event(pid, "storyboard", "memory_recall", "succeeded", agent="Director",
                   artifact=(f"{len(established)} facts recalled" if established
                             else "no prior facts"))
        # Feed the generator the ACTUAL scene — its written dialogue, stage
        # directions, cast and location — not just a one-line summary. Without
        # this the shot-writer invents shots and paraphrases the dialogue.
        scene_data = {
            "scene_number": scene.number,
            "heading": scene.heading,
            "location": scene.location,
            "description": scene.description,
            "emotional_beat": scene.emotional_beat,
            "characters_present": scene.characters_json or [],
            "stage_directions": scene.stage_directions or [],
            "dialogue": scene.dialogue_json or [],
            # what earlier scenes established — shots must not contradict it
            "established_facts": established,
        }

        tool_event(pid, "storyboard", "shot_breakdown", "started",
                   agent="Director", index=scene_index, total=len(scenes))
        with track_project(script.project_id, db):
            shots_data = await generator.generate_for_scene(
                scene_data, scene_chars,
                max_shots=shots_per_scene, shot_seconds=shot_seconds,
            )
            # Pin the background down: which props every shot of this scene
            # must render identically, and how the action changes them.
            # An enhancement — never fail the storyboard over it.
            try:
                from app.services.set_dresser import SetDresser

                tool_event(pid, "storyboard", "set_design", "started",
                           agent="Director", index=scene_index, total=len(scenes))
                scene.set_json = await SetDresser().dress(
                    scene_data,
                    [{"shot_number": sd.get("shot_number"),
                      "action": sd.get("action"),
                      "dialogue": sd.get("dialogue")} for sd in shots_data],
                )
                dressed += 1
                # ── narrative memory WRITE: prop-state changes become Facts,
                # known by everyone in the scene — recalled by later scenes ──
                sync_scene_facts(
                    pid, scene.number,
                    (scene.set_json or {}).get("state_changes") or [],
                    [c.get("name") for c in scene_chars if c.get("name")])
            except Exception:
                pass

        for shot_data in shots_data:
            in_frame = shot_data.get("characters_in_frame", []) or []
            # foreground names must be a subset of who is actually in frame
            foreground = [n for n in (shot_data.get("foreground_characters") or [])
                          if n in in_frame]
            shot = Shot(
                scene_id=scene.id,
                number=shot_data.get("shot_number", 1),
                shot_type=shot_data.get("shot_type"),
                camera_movement=shot_data.get("camera_movement"),
                lighting=shot_data.get("lighting"),
                colour_mood=shot_data.get("colour_mood"),
                action=shot_data.get("action"),
                dialogue=shot_data.get("dialogue"),
                emotional_beat=shot_data.get("emotional_beat"),
                estimated_duration_seconds=shot_data.get("estimated_duration_seconds", 5),
                characters_in_frame=in_frame,
                foreground_characters=foreground,
                blocking_json=({"subjects": shot_data.get("subjects"),
                                "reverse_angle": bool(shot_data.get("reverse_angle"))}
                               if shot_data.get("subjects") else None),
                notes=shot_data.get("notes"),
            )
            db.add(shot)
            all_shots.append(shot)

    tool_event(pid, "storyboard", "shot_breakdown", "succeeded",
               agent="Director", artifact=f"{len(all_shots)} shots")
    tool_event(pid, "storyboard", "set_design", "succeeded",
               agent="Director", artifact=f"{dressed} scenes dressed")
    with tool_run(pid, "storyboard", "write_shots_db", "Director") as t:
        db.commit()
        t["artifact"] = f"{len(all_shots)} rows"
    for s in all_shots:
        db.refresh(s)

    # Location plates ride along: the scenes exist now, so every location
    # gets a background plate for the story map and reference stacks. Plates
    # are an enhancement — never fail the storyboard over them.
    try:
        from app.services.casting_director import ensure_location_plates

        emit("stage:progress", {"stage": "storyboard", "status": "update", "agent": "Director",
             "label": "Painting location plates"}, pid)
        with track_project(script.project_id, db):
            await ensure_location_plates(db, script.project_id)
    except Exception:
        import logging

        logging.getLogger(__name__).warning(
            "location plate generation failed after storyboard", exc_info=True
        )

    emit("stage:progress", {"stage": "storyboard", "status": "completed", "agent": "Director",
         "label": f"Storyboard ready: {len(all_shots)} shots across {len(scenes)} scene(s)"}, pid)

    return {
        "total_shots": len(all_shots),
        "shots": [ShotResponse.model_validate(s) for s in all_shots],
    }


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
    result = []
    for scene in scenes:
        shots = db.query(Shot).filter(Shot.scene_id == scene.id).order_by(Shot.number).all()
        set_json = getattr(scene, "set_json", None) or {}
        result.append({
            "scene_number": scene.number,
            "heading": scene.heading,
            "set_items": set_json.get("set_items") or [],
            "state_changes": set_json.get("state_changes") or [],
            "shots": [ShotResponse.model_validate(s).model_dump() for s in shots],
        })
    return {"scenes": result}


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
