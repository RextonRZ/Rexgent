"""Canonical pipeline stage operations shared by the LangGraph agent.

These mirror the per-stage HTTP routers but are callable directly by the
autonomous agent. Each takes a DB session and returns plain dicts.
"""
import uuid
from sqlalchemy.orm import Session
from app.models.script import Script, Scene
from app.models.character import Character
from app.models.shot import Shot
from app.models.generation_job import GenerationJob
from app.services.script_generator import ScriptGenerator
from app.services.script_structurer import ScriptStructurer
from app.services.character_extractor import CharacterExtractor
from app.services.storyboard_generator import StoryboardGenerator, plan_shot_budget
from app.services.guardrails import InputSanitizer
from app.mcp_tools.token_optimizer import TokenOptimizer
from app.graph.sync import sync_scenes, sync_characters


def _persist_script(db: Session, project_id: str, raw_text: str, structured: dict) -> tuple[Script, dict]:
    script = Script(project_id=uuid.UUID(project_id), raw_text=raw_text, structured_json=structured)
    db.add(script)
    db.flush()
    scene_uuids: dict = {}
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
        scene_uuids[scene.number] = str(scene.id)
    db.commit()
    db.refresh(script)
    return script, scene_uuids


async def generate_script_op(
    db: Session, project_id: str, premise: str, genre: str,
    tone: str = "dramatic", episode_count: int = 1, target_length: int = 30,
    language: str = "en",
) -> dict:
    from app.services.usage_tracker import current_project
    _tok = current_project.set((str(project_id), db))
    try:
        clean_premise = InputSanitizer().sanitize(premise, max_length=300)
        raw_text = await ScriptGenerator().generate(
            genre=genre, premise=clean_premise, tone=tone,
            episode_count=episode_count, target_length=target_length, language=language,
        )
        structured = await ScriptStructurer().structure(raw_text, language=language)
        script, scene_uuids = _persist_script(db, project_id, raw_text, structured)
        sync_scenes(project_id, structured, scene_uuids=scene_uuids)
        return {"script_id": str(script.id), "structured": structured}
    finally:
        current_project.reset(_tok)


async def extract_characters_op(db: Session, script_id: str, infer_mbti: bool = False) -> list[dict]:
    script = db.query(Script).filter(Script.id == uuid.UUID(script_id)).first()
    if not script or not script.structured_json:
        return []
    from app.services.usage_tracker import current_project
    _tok = current_project.set((str(script.project_id), db))
    try:
        data = await CharacterExtractor().extract(script.structured_json)
    finally:
        current_project.reset(_tok)
    db.query(Character).filter(Character.project_id == script.project_id).delete()
    created = []
    for cd in data:
        c = Character(
            project_id=script.project_id, name=cd.get("name", "Unknown"),
            role=cd.get("role"), gender=cd.get("gender"),
            estimated_age=cd.get("estimated_age"),
            physical_description=cd.get("physical_description"),
            personality_summary=cd.get("personality_summary"),
            speech_pattern=cd.get("speech_pattern"),
            emotional_arc=cd.get("emotional_arc"),
            visual_description=cd.get("physical_description") or "",
            video_prompt_fragment=cd.get("physical_description") or "",
        )
        db.add(c)
        created.append(c)
    db.commit()
    for c in created:
        db.refresh(c)
    sync_characters(str(script.project_id), created, script.structured_json)
    return [{"id": str(c.id), "name": c.name, "role": c.role} for c in created]


async def generate_storyboard_op(db: Session, script_id: str, target_length: int = 30) -> list[dict]:
    script = db.query(Script).filter(Script.id == uuid.UUID(script_id)).first()
    if not script:
        return []
    scenes = db.query(Scene).filter(Scene.script_id == script.id).order_by(Scene.number).all()
    characters = db.query(Character).filter(Character.project_id == script.project_id).all()
    char_map = {c.name.upper(): {"name": c.name, "role": c.role, "visual_description": c.visual_description or ""} for c in characters}

    scene_ids = [s.id for s in scenes]
    db.query(Shot).filter(Shot.scene_id.in_(scene_ids)).delete(synchronize_session=False)

    shots_per_scene, shot_seconds = plan_shot_budget(len(scenes), target_length)
    gen = StoryboardGenerator()
    created = []
    from app.services.usage_tracker import current_project
    _tok = current_project.set((str(script.project_id), db))
    try:
        for scene in scenes:
            scene_chars = [char_map.get(str(n).upper(), {"name": n}) for n in (scene.characters_json or [])]
            shots = await gen.generate_for_scene(
                {"scene_number": scene.number, "heading": scene.heading,
                 "description": scene.description, "emotional_beat": scene.emotional_beat},
                scene_chars,
                max_shots=shots_per_scene,
                shot_seconds=shot_seconds,
            )
            for sd in shots:
                shot = Shot(
                    scene_id=scene.id, number=sd.get("shot_number", 1),
                    shot_type=sd.get("shot_type"), camera_movement=sd.get("camera_movement"),
                    lighting=sd.get("lighting"), colour_mood=sd.get("colour_mood"),
                    action=sd.get("action"), dialogue=sd.get("dialogue"),
                    emotional_beat=sd.get("emotional_beat"),
                    estimated_duration_seconds=sd.get("estimated_duration_seconds", 5),
                    characters_in_frame=sd.get("characters_in_frame", []),
                    notes=sd.get("notes"),
                )
                db.add(shot)
                created.append(shot)
    finally:
        current_project.reset(_tok)
    db.commit()
    return [{"shot_id": str(s.id), "shot_type": s.shot_type,
             "emotional_beat": s.emotional_beat,
             "characters_in_frame": s.characters_in_frame or [],
             "dialogue": s.dialogue,
             "estimated_duration_seconds": s.estimated_duration_seconds} for s in created]


def allocate_budget_op(db: Session, project_id: str, shots: list[dict], budget_usd: float | None = None) -> dict:
    if budget_usd is None:
        from app.models.project import Project
        project = db.query(Project).filter(Project.id == uuid.UUID(str(project_id))).first()
        budget_usd = float(project.credit_budget) if project and project.credit_budget else 40.0
    result = TokenOptimizer().allocate(shots, budget_usd)
    tier_by_id = {s["shot_id"]: s["quality_tier"] for s in result["scored_shots"]}
    for sid, tier in tier_by_id.items():
        shot = db.query(Shot).filter(Shot.id == uuid.UUID(sid)).first()
        if shot:
            shot.quality_tier = tier
    db.commit()
    from app.agents.reporter import report_agent
    report_agent(db, project_id, agent="budget_allocator", stage="budget",
                 decision={"wan": result.get("wan_shots"), "happyhorse": result.get("happyhorse_shots")}
                         if isinstance(result, dict) else {},
                 rationale="Allocated quality tiers under the cap", confidence=1.0)
    return result


async def cast_bible_op(db: Session, project_id: str) -> dict:
    from app.services.casting_director import CastingDirector
    return await CastingDirector(db).cast_bible(project_id)


async def synth_dialogue_op(db: Session, project_id: str) -> int:
    from app.services.dialogue_synthesizer import DialogueSynthesizer
    from app.models.script import Script, Scene
    from app.models.character import Character
    from app.models.line_audio import LineAudio
    script = (db.query(Script).filter(Script.project_id == uuid.UUID(str(project_id)))
              .order_by(Script.created_at.desc()).first())
    if not script:
        return 0
    scenes = db.query(Scene).filter(Scene.script_id == script.id).order_by(Scene.number).all()
    chars = db.query(Character).filter(Character.project_id == uuid.UUID(str(project_id))).all()
    # Assign a distinct preset voice to any character that skipped casting, so the
    # export isn't every character speaking in the same fallback voice.
    from app.services.casting_director import assign_voice
    changed = False
    for i, c in enumerate(chars):
        if not c.voice_id:
            assign_voice(c, i)
            changed = True
    if changed:
        db.commit()
    voice_by_name = {c.name: {"voice_id": c.voice_id, "voice_model": c.voice_model} for c in chars}
    scene_dicts = [{"number": s.number, "dialogue_json": s.dialogue_json} for s in scenes]
    rows = await DialogueSynthesizer(db).synthesize_lines(project_id, scene_dicts, voice_by_name)
    db.query(LineAudio).filter(LineAudio.project_id == uuid.UUID(str(project_id))).delete()
    for r in rows:
        db.add(LineAudio(**r))
    db.commit()
    from app.agents.reporter import report_agent
    report_agent(db, project_id, agent="audio_continuity", stage="audio",
                 decision={"lines": len(rows)},
                 rationale=f"Synthesized {len(rows)} dialogue lines", confidence=1.0)
    return len(rows)


async def clarify_op(db: Session, project_id: str) -> dict:
    from app.agents.clarification_agent import ClarificationAgent, needs_pause
    from app.agents.reporter import report_agent
    from app.models.project import Project
    from app.models.script import Script
    from app.models.character import Character
    from app.websocket.emitter import emit
    script = (db.query(Script).filter(Script.project_id == uuid.UUID(str(project_id)))
              .order_by(Script.created_at.desc()).first())
    chars = db.query(Character).filter(Character.project_id == uuid.UUID(str(project_id))).all()
    assessment = await ClarificationAgent().assess(
        (script.structured_json if script else {}) or {},
        [{"name": c.name, "physical_description": c.physical_description} for c in chars])
    project = db.query(Project).filter(Project.id == uuid.UUID(str(project_id))).first()
    pause = needs_pause(assessment, bool(project.auto_clarify) if project else False)
    report_agent(db, project_id, agent="clarification", stage="clarify",
                 decision=assessment,
                 rationale=("awaiting user answers" if pause else "no blocking ambiguity / auto-assumed"),
                 confidence=assessment.get("confidence", 1.0))
    if pause:
        emit("clarification.awaiting", {"questions": assessment["ambiguities"]}, str(project_id))
    return {"pause": pause, "assessment": assessment}


def dispatch_generation_op(db: Session, project_id: str) -> str:
    job = GenerationJob(project_id=uuid.UUID(project_id))
    db.add(job)
    db.commit()
    db.refresh(job)
    from app.workers.generation_worker import run_generation_job
    run_generation_job.delay(str(job.id))
    return str(job.id)
