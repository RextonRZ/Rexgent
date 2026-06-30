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
from app.services.storyboard_generator import StoryboardGenerator
from app.services.guardrails import InputSanitizer
from app.mcp_tools.token_optimizer import TokenOptimizer
from app.graph.sync import sync_scenes, sync_characters


def _persist_script(db: Session, project_id: str, raw_text: str, structured: dict) -> Script:
    script = Script(project_id=uuid.UUID(project_id), raw_text=raw_text, structured_json=structured)
    db.add(script)
    db.flush()
    for sc in structured.get("scenes", []):
        db.add(Scene(
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
        ))
    db.commit()
    db.refresh(script)
    return script


async def generate_script_op(
    db: Session, project_id: str, premise: str, genre: str,
    tone: str = "dramatic", episode_count: int = 1, target_length: int = 30,
    language: str = "en",
) -> dict:
    clean_premise = InputSanitizer().sanitize(premise, max_length=300)
    raw_text = await ScriptGenerator().generate(
        genre=genre, premise=clean_premise, tone=tone,
        episode_count=episode_count, target_length=target_length, language=language,
    )
    structured = await ScriptStructurer().structure(raw_text, language=language)
    script = _persist_script(db, project_id, raw_text, structured)
    sync_scenes(project_id, structured)
    return {"script_id": str(script.id), "structured": structured}


async def extract_characters_op(db: Session, script_id: str, infer_mbti: bool = False) -> list[dict]:
    script = db.query(Script).filter(Script.id == uuid.UUID(script_id)).first()
    if not script or not script.structured_json:
        return []
    data = await CharacterExtractor().extract(script.structured_json)
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


async def generate_storyboard_op(db: Session, script_id: str) -> list[dict]:
    script = db.query(Script).filter(Script.id == uuid.UUID(script_id)).first()
    if not script:
        return []
    scenes = db.query(Scene).filter(Scene.script_id == script.id).order_by(Scene.number).all()
    characters = db.query(Character).filter(Character.project_id == script.project_id).all()
    char_map = {c.name.upper(): {"name": c.name, "role": c.role, "visual_description": c.visual_description or ""} for c in characters}

    scene_ids = [s.id for s in scenes]
    db.query(Shot).filter(Shot.scene_id.in_(scene_ids)).delete(synchronize_session=False)

    gen = StoryboardGenerator()
    created = []
    for scene in scenes:
        scene_chars = [char_map.get(str(n).upper(), {"name": n}) for n in (scene.characters_json or [])]
        shots = await gen.generate_for_scene(
            {"scene_number": scene.number, "heading": scene.heading,
             "description": scene.description, "emotional_beat": scene.emotional_beat},
            scene_chars,
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
    db.commit()
    return [{"shot_id": str(s.id), "shot_type": s.shot_type,
             "emotional_beat": s.emotional_beat,
             "characters_in_frame": s.characters_in_frame or [],
             "dialogue": s.dialogue,
             "estimated_duration_seconds": s.estimated_duration_seconds} for s in created]


def allocate_budget_op(db: Session, project_id: str, shots: list[dict], budget_usd: float = 40.0) -> dict:
    result = TokenOptimizer().allocate(shots, budget_usd)
    tier_by_id = {s["shot_id"]: s["quality_tier"] for s in result["scored_shots"]}
    for sid, tier in tier_by_id.items():
        shot = db.query(Shot).filter(Shot.id == uuid.UUID(sid)).first()
        if shot:
            shot.quality_tier = tier
    db.commit()
    return result


def dispatch_generation_op(db: Session, project_id: str) -> str:
    job = GenerationJob(project_id=uuid.UUID(project_id))
    db.add(job)
    db.commit()
    db.refresh(job)
    from app.workers.generation_worker import run_generation_job
    run_generation_job.delay(str(job.id))
    return str(job.id)
