import re
from sqlalchemy.orm import Session
from app.models.script import Script, Scene
from app.models.character import Character
from app.models.project import Project
from app.models.costume_variant import CostumeVariant
from app.models.location_plate import LocationPlate
from app.models.style_preset import StylePreset
from app.services.wardrobe_planner import WardrobePlanner
from app.services.plate_generator import (PlateGenerator, character_plate_prompt,
                                          subject_descriptor, CHAR_PLATE_NEGATIVE)
from app.services.prompt_loader import load_prompt
from app.services.guardrails import strip_character_names
from app.websocket.emitter import emit
from app.websocket.tool_events import tool_event, tool_run


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "").strip().lower()).strip("_")


def distinct_locations(scenes: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for sc in scenes:
        k = _key(sc.get("location", "")) or "unknown"
        g = grouped.setdefault(k, {"location_key": k, "description": sc.get("location", ""), "scene_numbers": []})
        g["scene_numbers"].append(sc.get("number"))
    return list(grouped.values())


async def style_from_request(qwen, prompt_template: str, free_text: str) -> dict:
    result = await qwen.chat_json(messages=[
        {"role": "system", "content": prompt_template},
        {"role": "user", "content": free_text or "cinematic realistic drama"},
    ], temperature=0.4, task="style")
    return result if isinstance(result, dict) else {"style_tags": [], "prompt": free_text, "negative_prompt": ""}


# Back-compat: a flat pool of clean general-purpose presets. The full catalog
# (with gender + descriptions) lives in app.services.voice_catalog.
from app.services.voice_catalog import FEMALE_DEFAULTS, MALE_DEFAULTS, default_voice
VOICE_POOL = FEMALE_DEFAULTS + MALE_DEFAULTS


async def ensure_location_plates(db: Session, project_id) -> int:
    """Generate background plates for scene locations that don't have one
    yet. Idempotent — existing plates are never touched — so the storyboard
    flow can call it after every (re)generation. Returns how many were made."""
    script = (db.query(Script).filter(Script.project_id == project_id)
              .order_by(Script.created_at.desc()).first())
    if not script:
        return 0
    scenes = (db.query(Scene).filter(Scene.script_id == script.id)
              .order_by(Scene.number).all())
    scene_dicts = [{"number": s.number, "location": s.location} for s in scenes]

    existing = {p.location_key for p in db.query(LocationPlate)
                .filter(LocationPlate.project_id == project_id).all()}
    missing = [loc for loc in distinct_locations(scene_dicts)
               if loc["location_key"] not in existing
               and (loc["description"] or "").strip()]
    if not missing:
        return 0

    pid = str(project_id)
    plates = PlateGenerator(db)
    style = db.query(StylePreset).filter(StylePreset.project_id == project_id).first()
    tags = list(style.style_tags or []) if style else []
    # a location like "Bear's apartment" must not paint the animal Bear —
    # neutralize character names in the plate prompt (label stays raw in the DB)
    char_names = [c.name for c in
                  db.query(Character).filter(Character.project_id == project_id).all()]

    for idx, loc in enumerate(missing, start=1):
        emit("casting.plate.started",
             {"kind": "location", "key": loc["location_key"], "index": idx, "total": len(missing)}, pid)
        tool_event(pid, "characters", "generate_plates", "started", agent="Casting",
                   index=idx, total=len(missing))
        desc = strip_character_names(loc["description"], char_names) or "interior room"
        prompt = f"{desc} background plate"
        if tags:
            prompt += f". {', '.join(tags)}"
        url, _ = await plates.generate_and_store_plate(pid, "location", loc["location_key"], prompt)
        db.add(LocationPlate(project_id=project_id, location_key=loc["location_key"],
                             description=loc["description"], plate_image_url=url,
                             scene_numbers=loc["scene_numbers"]))
        emit("casting.plate.completed",
             {"kind": "location", "key": loc["location_key"], "index": idx, "total": len(missing)}, pid)

    db.commit()
    tool_event(pid, "characters", "generate_plates", "succeeded", agent="Casting",
               artifact=f"{len(missing)} location plates")
    return len(missing)


def assign_voice(char, index: int = 0) -> None:
    """Assign a preset TTS voice (qwen3-tts-flash timbre), matched to the
    character's gender and rotated by index so each gets a distinct one.
    No API call — presets are just names."""
    if char.voice_id:
        return
    from app.config import get_settings
    char.voice_id = default_voice(getattr(char, "gender", None), index)
    char.voice_model = get_settings().qwen_tts_designed_model
    char.voice_source = "preset"


class CastingDirector:
    def __init__(self, db: Session):
        self.db = db
        self.planner = WardrobePlanner()
        self.plates = PlateGenerator(self.db)
        self.style_prompt = load_prompt("style_plate.txt")

    async def cast_bible(self, project_id) -> dict:
        pid = str(project_id)
        emit("casting.started", {}, pid)
        script = (self.db.query(Script).filter(Script.project_id == project_id)
                  .order_by(Script.created_at.desc()).first())
        scenes = self.db.query(Scene).filter(Scene.script_id == script.id).order_by(Scene.number).all()
        characters = self.db.query(Character).filter(Character.project_id == project_id).all()
        scene_dicts = [{"number": s.number, "location": s.location} for s in scenes]

        from app.services.usage_tracker import track_project
        with track_project(pid, self.db):
            # a character without a visual description would BLOCK generation
            # later (preflight) — users who skip face upload get one generated.
            # This IS the profile_cast tool running automatically, so the crew
            # graph node lights up instead of pretending nothing happened.
            needing_look = [c for c in characters
                            if not ((c.visual_description or "").strip()
                                    and (c.video_prompt_fragment or "").strip())]
            if needing_look:
                tool_event(pid, "characters", "profile_cast", "started",
                           agent="Casting", total=len(needing_look))
            looks_written = 0
            for c in needing_look:
                try:
                    from app.services.appearance_generator import AppearanceGenerator
                    look = await AppearanceGenerator().generate(
                        character_name=c.name, role=c.role or "SUPPORTING",
                        personality=c.personality_summary or "",
                        mbti=getattr(c, "mbti", "") or "",
                        physical_desc=c.physical_description or "")
                    c.visual_description = (c.visual_description or "").strip() or look.get("full_description", "")
                    c.video_prompt_fragment = (c.video_prompt_fragment or "").strip() or look.get("video_prompt_fragment", "")
                    looks_written += 1
                except Exception as e:  # noqa: BLE001
                    import logging
                    logging.getLogger(__name__).warning(f"appearance autofill skipped for {c.name}: {e}")
            if needing_look:
                tool_event(pid, "characters", "profile_cast", "succeeded",
                           agent="Casting", artifact=f"{looks_written} looks written")
            self.db.commit()
            plan = await self.planner.plan(script.structured_json or {},
                                           [{"name": c.name} for c in characters])
            emit("casting.wardrobe_plan.completed", {"variant_count": sum(len(v) for v in plan.values())}, pid)

            locations = distinct_locations(scene_dicts)
            style = await style_from_request(self.plates.qwen, self.style_prompt, self._style_input(project_id))

        total = 1 + len(locations) + sum(max(1, len(plan.get(c.name, []))) for c in characters)
        idx = 0

        idx += 1
        emit("casting.plate.started", {"kind": "style", "key": "style", "index": idx, "total": total}, pid)
        tool_event(pid, "characters", "generate_plates", "started", agent="Casting",
                   index=idx, total=total)
        s_url, _ = await self.plates.generate_and_store_plate(pid, "style", "style",
                                                              style.get("prompt", ""),
                                                              negative_prompt=style.get("negative_prompt"))
        self._upsert_style(project_id, style, s_url)
        emit("casting.plate.completed", {"kind": "style", "key": "style", "index": idx, "total": total}, pid)

        char_names = [c.name for c in characters]
        for loc in locations:
            idx += 1
            emit("casting.plate.started", {"kind": "location", "key": loc["location_key"], "index": idx, "total": total}, pid)
            tool_event(pid, "characters", "generate_plates", "started", agent="Casting",
                       index=idx, total=total)
            desc = strip_character_names(loc["description"], char_names) or "interior room"
            prompt = f"{desc} background plate. {', '.join(style.get('style_tags', []))}"
            url, _ = await self.plates.generate_and_store_plate(pid, "location", loc["location_key"], prompt)
            self.db.add(LocationPlate(project_id=project_id, location_key=loc["location_key"],
                                      description=loc["description"], plate_image_url=url,
                                      scene_numbers=loc["scene_numbers"]))
            emit("casting.plate.completed", {"kind": "location", "key": loc["location_key"], "index": idx, "total": total}, pid)

        faces_locked = 0
        for c in characters:
            variants = plan.get(c.name) or [{"label": "default", "outfit_description": "",
                                             "scene_numbers": []}]
            for i, v in enumerate(variants):
                idx += 1
                emit("casting.plate.started", {"kind": "character", "key": f"{c.name}:{v['label']}", "index": idx, "total": total}, pid)
                tool_event(pid, "characters", "generate_plates", "started", agent="Casting",
                           index=idx, total=total)
                outfit = v.get("outfit_description", "")
                # identity plate: waist-up, plain background, no style-tag scene drift
                subject = subject_descriptor(c.gender, c.estimated_age,
                                             c.physical_description or c.visual_description)
                prompt = character_plate_prompt(bool(c.reference_image_url), subject, outfit)
                url, vector = await self.plates.generate_and_store_plate(
                    pid, "character", f"{c.name}_{v['label']}", prompt,
                    negative_prompt=CHAR_PLATE_NEGATIVE,
                    base_image_url=c.reference_image_url, prompt_extend=False,
                    # verify the rendered face against the uploaded one
                    match_vector=c.face_vector if c.reference_image_url else None)
                if vector:
                    faces_locked += 1
                is_default = (i == 0)
                self.db.add(CostumeVariant(character_id=c.id, label=v["label"],
                                           outfit_description=v.get("outfit_description"),
                                           plate_image_url=url, face_vector=vector,
                                           scene_numbers=v.get("scene_numbers") or [],
                                           is_default=is_default, plate_status="ai_generated"))
                # Seed the identity from the default plate ONLY if the user hasn't set a
                # face reference — never clobber an uploaded face.
                if is_default and not c.reference_image_url:
                    c.reference_image_url = url
                    c.face_vector = vector
                    c.plate_status = "ai_generated"
                emit("casting.plate.completed", {"kind": "character", "key": f"{c.name}:{v['label']}", "index": idx, "total": total}, pid)

        tool_event(pid, "characters", "generate_plates", "succeeded", agent="Casting",
                   artifact=f"{total} plates")
        if faces_locked:
            tool_event(pid, "characters", "face_lock", "succeeded", agent="Casting",
                       artifact=f"{faces_locked} identities locked")

        with tool_run(pid, "characters", "voice_assign", "Casting",
                      total=len(characters)) as t:
            for idx_v, c in enumerate(characters):
                emit("casting.voice.started", {"character": c.name}, pid)
                assign_voice(c, idx_v)
                emit("casting.voice.completed", {"character": c.name}, pid)
            t["artifact"] = f"{len(characters)} voices"

        self.db.commit()
        from app.agents.reporter import report_agent
        report_agent(self.db, project_id, agent="style_casting", stage="casting",
                     decision={"plates_total": total},
                     rationale=f"Cast {total} plates", confidence=1.0)
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if project and project.auto_approve_casting:
            emit("casting.completed", {"plates_total": total, "auto_approved": True}, pid)
            return {"status": "auto_approved", "plates_total": total}
        emit("casting.awaiting_review", {}, pid)
        emit("casting.completed", {"plates_total": total, "auto_approved": False}, pid)
        return {"status": "awaiting_review", "plates_total": total}

    def _style_input(self, project_id) -> str:
        existing = self.db.query(StylePreset).filter(StylePreset.project_id == project_id).first()
        return (existing.free_text if existing else "") or "cinematic realistic drama"

    def _upsert_style(self, project_id, style: dict, url: str) -> None:
        row = self.db.query(StylePreset).filter(StylePreset.project_id == project_id).first()
        if not row:
            row = StylePreset(project_id=project_id)
            self.db.add(row)
        row.style_tags = style.get("style_tags", [])
        row.free_text = style.get("prompt", "")
        row.plate_image_url = url
        row.negative_prompt = style.get("negative_prompt", "")
