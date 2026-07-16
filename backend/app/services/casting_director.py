import logging
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
                                          subject_descriptor, CHAR_PLATE_NEGATIVE,
                                          char_plate_negative, clean_appearance)
from app.services.prompt_loader import load_prompt
from app.services.guardrails import strip_character_names
from app.config import get_settings

logger = logging.getLogger(__name__)
from app.websocket.emitter import emit
from app.websocket.tool_events import tool_event, tool_run


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "").strip().lower()).strip("_")


# View/position qualifiers the structurer prepends to a place name, split by
# which side of the walls they put the camera on. Longest first so "in front
# of" wins over "front of", "outside of" over "outside".
_EXT_QUALIFIERS = (
    "in front of", "entrance to", "entrance of", "exterior of", "outside of",
    "front of", "back of", "next to", "outside", "behind", "beside", "near",
)
_INT_QUALIFIERS = ("interior of", "inside of", "inside")
_VIEW_QUALIFIERS = tuple(sorted(_EXT_QUALIFIERS + _INT_QUALIFIERS,
                                key=len, reverse=True))


def location_family(name: str) -> str:
    """One PLACE, one family: collapse view/position qualifiers and articles
    so 'Front of Anna's Cabin', 'inside the cabin' and 'Anna's Cabin' key the
    same family — two independently painted images of one place never look
    like the same place."""
    low = re.sub(r"\s+", " ", str(name or "").strip().lower())
    while True:
        trimmed = re.sub(r"^(?:the|a|an)\s+", "", low)
        for q in _VIEW_QUALIFIERS:
            if trimmed.startswith(q + " "):
                trimmed = trimmed[len(q):].strip()
                break
        if trimmed == low:
            break
        low = trimmed
    return _key(low)


def location_view(location: str, heading=None) -> str | None:
    """'int' / 'ext' / None — which side of the walls the camera is on. The
    location's own qualifier ('front of', 'inside') outranks the heading:
    screenwriters mislabel INT/EXT (a headlights-outside scene shipped under
    INT.), but a view qualifier in the location text is deliberate."""
    low = re.sub(r"\s+", " ", str(location or "").strip().lower())
    trimmed = re.sub(r"^(?:the|a|an)\s+", "", low)
    for q in _VIEW_QUALIFIERS:
        if trimmed.startswith(q + " "):
            return "ext" if q in _EXT_QUALIFIERS else "int"
    up = str(heading or "").strip().upper()
    if up.startswith("INT"):
        return "int"
    if up.startswith("EXT"):
        return "ext"
    return None


def distinct_locations(scenes: list[dict]) -> list[dict]:
    """Group scenes by location family AND view, so one place paints one plate
    per side of its walls: same-view scenes share a plate (consistency), but
    interior and exterior never merge — the plate is rendered on screen as
    the set (reference_stack attaches it on room-showing framings), and an
    exterior shot anchored to an interior room is simply the wrong image.
    The shortest raw name in a group paints it; the first heading provides
    its time hint."""
    grouped: dict[str, dict] = {}
    for sc in scenes:
        raw = str(sc.get("location", "") or "")
        view = location_view(raw, sc.get("heading"))
        fam = location_family(raw) or "unknown"
        k = f"{fam}__{view}" if view else fam
        g = grouped.setdefault(k, {"location_key": k, "description": raw,
                                   "heading": sc.get("heading"), "view": view,
                                   "scene_numbers": []})
        g["scene_numbers"].append(sc.get("number"))
        if raw and (not g["description"] or len(raw) < len(g["description"])):
            g["description"] = raw
        if not g.get("heading"):
            g["heading"] = sc.get("heading")
    return list(grouped.values())


_HEADING_TIMES = {"night", "day", "morning", "evening", "dusk", "dawn",
                  "sunset", "sunrise", "afternoon", "noon", "midnight",
                  "golden hour"}

# a plate is the EMPTY stage the cast renders onto — a person baked into it
# comes back in every shot of that location
LOCATION_PLATE_NEGATIVE = "people, person, faces, figures, crowd, text, watermark"


def _heading_hints(heading) -> tuple[str | None, str | None]:
    """(interior/exterior, time of day) parsed from a screenplay heading like
    'INT. ANNA'S CABIN - NIGHT'. 'LATER'/'CONTINUOUS' are not lighting."""
    up = str(heading or "").strip().upper()
    place = ("interior" if up.startswith("INT")
             else "exterior" if up.startswith("EXT") else None)
    time = None
    if "-" in up:
        t = up.rsplit("-", 1)[-1].strip().lower()
        if t in _HEADING_TIMES:
            time = t
    return place, time


def location_plate_prompt(desc: str, heading=None, tags=None, view=None) -> str:
    """The location plate's image prompt. A bare '{name} background plate'
    painted a different-looking place every run; the interior/exterior view
    and the heading's time of day pin the plate to the scenes it backs, and
    the plate is explicitly unpopulated. `view` ('int'/'ext', from the
    location group) outranks the heading's INT/EXT."""
    place, time = _heading_hints(heading)
    place = {"int": "interior", "ext": "exterior"}.get(view) or place
    bits = [str(desc or "").strip() or "interior room",
            (f"empty {place} establishing background plate" if place
             else "empty establishing background plate")]
    if time:
        bits.append(f"{time} lighting")
    bits.append("no people, no characters in view")
    prompt = ", ".join(bits)
    if tags:
        prompt += f". {', '.join(tags)}"
    return prompt


def style_look_clause(genre: str | None) -> str:
    """A style-director hint that pins the style plate to the Director's genre
    look (the same LookProfile the per-shot stylization reads), so the style
    plate image and the per-shot look don't diverge."""
    from app.director.recommender import recommend_look
    look = recommend_look(genre)
    return (f"Consistent with a {look.stylization} look: {look.lighting}, "
            f"{look.colour_mood}, {look.light_quality} light.")


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


def voice_design_prompt(char) -> str:
    """The character sheet, folded into a voice description: age, gender,
    personality and role shape a bespoke timbre instead of a rotated preset."""
    bits = []
    age = getattr(char, "estimated_age", None)
    gender = getattr(char, "gender", None)
    lead = "A"
    if age and gender:
        lead = f"A {gender} around {age} years old,"
    elif gender:
        lead = f"A {gender},"
    elif age:
        lead = f"A person around {age} years old,"
    bits.append(lead)
    persona = (getattr(char, "personality_summary", None) or "").strip()
    if persona:
        bits.append(f"personality: {persona[:400]}.")
    bits.append("Natural conversational voice for a drama, emotionally expressive, "
                "clear diction, speaks English.")
    return " ".join(bits)[:2000]


def design_voice(char, db=None, project_id=None) -> bool:
    """qwen-voice-design: create a voice matched to THIS character. Returns
    True when the designed voice is assigned; False falls back to presets."""
    import re as _re2
    import httpx
    from app.config import get_settings
    from app.services.api_keys import resolve_qwen_key, MissingApiKey
    s = get_settings()
    try:
        key = resolve_qwen_key(s)
    except MissingApiKey:
        return False
    if not key:
        return False
    name = _re2.sub(r"[^a-z0-9]", "", str(getattr(char, "name", "voice")).lower())[:10] or "voice"
    try:
        r = httpx.post(
            s.qwen_video_base_url + "/services/audio/tts/customization",
            json={"model": s.qwen_voice_design_model,
                  "input": {"action": "create",
                            "target_model": s.qwen_tts_vd_model,
                            "preferred_name": name,
                            "voice_prompt": voice_design_prompt(char),
                            "preview_text": "This is how I sound."},
                  "parameters": {"sample_rate": 24000, "response_format": "wav"}},
            headers={"Authorization": f"Bearer {key}"}, timeout=120.0)
        voice = (r.json().get("output") or {}).get("voice") if r.status_code == 200 else None
        if not voice:
            raise RuntimeError(f"{r.status_code}: {r.text[:150]}")
        char.voice_id = voice
        char.voice_model = s.qwen_tts_vd_model
        char.voice_source = "designed"
        if db is not None and project_id is not None:
            from app.services.cost_ledger import record
            record(db, project_id, "tts", "casting", "voice", 1, 0.2,
                   model=s.qwen_voice_design_model)
        return True
    except Exception as e:  # noqa: BLE001 — casting must never block on a voice
        logger.warning("voice design failed for %s: %s", getattr(char, "name", "?"), e)
        return False


def assign_voice(char, index: int = 0, db=None, project_id=None) -> None:
    """Give the character a voice: DESIGN one from their character sheet
    (age/gender/personality matched); fall back to a gender-matched preset
    rotated by index when the design service is unavailable. Designing spends
    real money ($0.20/voice) — it fires only with a db to ledger it AND when
    the TTS overlay is actually in use."""
    if char.voice_id:
        return
    from app.config import get_settings
    if (db is not None and getattr(get_settings(), "tts_overlay", False)
            and design_voice(char, db=db, project_id=project_id)):
        return
    char.voice_id = default_voice(getattr(char, "gender", None), index)
    char.voice_model = get_settings().qwen_tts_designed_model
    char.voice_source = "preset"


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
    scene_dicts = [{"number": s.number, "location": s.location,
                    "heading": s.heading} for s in scenes]

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
        # staged under STORYBOARD in the crew graph: location plates paint at
        # boarding time now, not on the Characters tab
        tool_event(pid, "storyboard", "location_plates", "started", agent="Casting",
                   index=idx, total=len(missing))
        desc = strip_character_names(loc["description"], char_names) or "interior room"
        prompt = location_plate_prompt(desc, heading=loc.get("heading"),
                                       tags=tags, view=loc.get("view"))
        url, _ = await plates.generate_and_store_plate(
            pid, "location", loc["location_key"], prompt,
            negative_prompt=LOCATION_PLATE_NEGATIVE)
        db.add(LocationPlate(project_id=project_id, location_key=loc["location_key"],
                             description=loc["description"], plate_image_url=url,
                             scene_numbers=loc["scene_numbers"]))
        emit("casting.plate.completed",
             {"kind": "location", "key": loc["location_key"], "index": idx, "total": len(missing)}, pid)

    db.commit()
    tool_event(pid, "storyboard", "location_plates", "succeeded", agent="Casting",
               artifact=f"{len(missing)} location plates")
    return len(missing)


async def ensure_style_plate(db: Session, project_id) -> bool:
    """Paint the style plate at STORYBOARD time (not casting), image-edited
    FROM the lead character's plate so the style frame shows the real cast
    face instead of an invented person. Idempotent: an existing style image is
    never repainted. Returns True when a plate was painted."""
    style = db.query(StylePreset).filter(StylePreset.project_id == project_id).first()
    if style is None or (style.plate_image_url or "").strip():
        return False
    # the lead's default plate seeds the edit (the image API takes ONE base
    # image, so the style frame carries one real face — the protagonist)
    chars = db.query(Character).filter(Character.project_id == project_id).all()
    chars.sort(key=lambda c: 0 if str(c.role or "").upper() == "PROTAGONIST" else 1)
    base_url = None
    for c in chars:
        for v in db.query(CostumeVariant).filter(CostumeVariant.character_id == c.id).all():
            if v.plate_image_url:
                base_url = v.plate_image_url
                break
        if base_url:
            break
    prompt = ((style.free_text or "cinematic realistic drama").strip()
              + ". A cinematic film still of the SAME person as the reference "
                "image - keep the identical face and hair - placed in this "
                "visual style.")
    pid = str(project_id)
    plates = PlateGenerator(db)
    tool_event(pid, "storyboard", "style_plate", "started", agent="Casting")
    url, _ = await plates.generate_and_store_plate(
        pid, "style", "style", prompt,
        negative_prompt=style.negative_prompt or None,
        base_image_url=base_url)
    style.plate_image_url = url
    db.commit()
    tool_event(pid, "storyboard", "style_plate", "succeeded", agent="Casting",
               artifact="style frame from the lead's plate" if base_url else "style frame")
    emit("casting.plate.completed", {"kind": "style", "key": "style"}, pid)
    return True


import re as _re
# Face-COVERING eyewear/masks occlude the locked face: they tank ArcFace scores
# and flicker between framings (a zoom-in makes the lab glasses vanish). Plain
# prescription glasses/spectacles are fine and kept.
_FACE_OBSCURING = _re.compile(
    r"\b(sun\s?glasses|goggles|safety\s+glasses|lab\s+glasses|ski\s+goggles|"
    r"face\s+mask|gas\s+mask|welding\s+mask|ski\s+mask|balaclava|visor|"
    r"tinted\s+(glasses|lenses|shades)|shades|vr\s+headset|blindfold|"
    r"eye\s+patch)\b", _re.I)


def _strip_face_obscuring_eyewear(outfit: str) -> str:
    """Drop face-covering accessories from a comma-listed outfit; keep the rest."""
    kept = [p.strip() for p in (outfit or "").split(",")
            if p.strip() and not _FACE_OBSCURING.search(p)]
    return ", ".join(kept)


def resolve_outfit(scene_outfit: str | None, default_clothing: str | None) -> str:
    """Clothing ownership: the wardrobe's per-scene outfit wins; when a scene
    has none, fall back to the character's default clothing (appearance's
    clothing_keywords). The appearance FRAGMENT no longer carries clothing, so
    without this fallback an unwardrobed scene renders the character naked.
    Face-obscuring eyewear/masks are stripped — they break face consistency."""
    resolved = (scene_outfit or "").strip() or (default_clothing or "").strip()
    return _strip_face_obscuring_eyewear(resolved)


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
        scene_dicts = [{"number": s.number, "location": s.location,
                        "heading": s.heading} for s in scenes]

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
            # the appearance fragment now carries ONLY permanent traits (no
            # clothing), so a scene with no wardrobe outfit would render the
            # character with no clothes — clothing_keywords is their DEFAULT
            # outfit, used to backfill any empty wardrobe slot below
            default_clothing: dict = {}
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
                    clothes = ", ".join(look.get("clothing_keywords") or [])
                    if clothes.strip():
                        default_clothing[c.name] = clothes.strip()
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

        # Style TAGS are computed here (the costume plates need them), but the
        # style IMAGE and the location plates are NOT painted at casting: they
        # render at storyboard time (ensure_location_plates / ensure_style_plate)
        # — the Characters tab's "Generate plates" spends only on the cast, and
        # the style image can then be built FROM a cast plate so it shows the
        # real lead instead of an invented person.
        _ = locations  # location plates paint at boarding via ensure_location_plates
        total = sum(max(1, len(plan.get(c.name, []))) for c in characters)
        idx = 0
        self._upsert_style(project_id, style, None)

        faces_locked = 0
        for c in characters:
            variants = plan.get(c.name) or [{"label": "default", "outfit_description": "",
                                             "scene_numbers": []}]
            for i, v in enumerate(variants):
                idx += 1
                emit("casting.plate.started", {"kind": "character", "key": f"{c.name}:{v['label']}", "index": idx, "total": total}, pid)
                tool_event(pid, "characters", "generate_plates", "started", agent="Casting",
                           index=idx, total=total)
                # wardrobe outfit wins; when a scene has none, fall back to the
                # character's default clothing so they're never rendered naked
                outfit = resolve_outfit(v.get("outfit_description"), default_clothing.get(c.name))
                # identity plate: waist-up, plain background, no style-tag scene drift
                # physical_description sometimes carries a SCENE moment ("clutching
                # a photo, crying, soaked"); clean it and fall back to the structural
                # visual_description so the plate stays a static identity look.
                subject = subject_descriptor(
                    c.gender, c.estimated_age,
                    clean_appearance(c.physical_description) or clean_appearance(c.visual_description))
                prompt = character_plate_prompt(bool(c.reference_image_url), subject, outfit)
                url, vector = await self.plates.generate_and_store_plate(
                    pid, "character", f"{c.name}_{v['label']}", prompt,
                    negative_prompt=char_plate_negative(
                        c.visual_description, c.physical_description,
                        c.video_prompt_fragment, outfit),
                    base_image_url=c.reference_image_url, prompt_extend=False,
                    # verify the rendered face against the uploaded one
                    match_vector=c.face_vector if c.reference_image_url else None)
                if vector:
                    faces_locked += 1
                is_default = (i == 0)
                # the reference photo was REJECTED by the edit model's content
                # inspection (e.g. a recognizable public figure): say so on the
                # plate instead of quietly showing an invented stranger
                status = ("ref_rejected"
                          if self.plates.last_face_preserved is False
                          else "ai_generated")
                if status == "ref_rejected":
                    emit("casting.plate.warning",
                         {"kind": "character", "key": f"{c.name}:{v['label']}",
                          "reason": "reference photo rejected by the image "
                                    "service's content filter"}, pid)
                self.db.add(CostumeVariant(character_id=c.id, label=v["label"],
                                           # persist the backfilled outfit so the
                                           # render's per-scene lookup gets clothing too
                                           outfit_description=outfit or None,
                                           plate_image_url=url, face_vector=vector,
                                           scene_numbers=v.get("scene_numbers") or [],
                                           is_default=is_default, plate_status=status))
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
        base = (existing.free_text if existing else "") or "cinematic realistic drama"
        # Under the Director engine, align the style plate with the genre look so
        # the two style channels (plate image + per-shot stylization) agree.
        if getattr(get_settings(), "director_engine", False):
            proj = self.db.query(Project).filter(Project.id == project_id).first()
            base = f"{base}. {style_look_clause(getattr(proj, 'genre', None))}"
        return base

    def _upsert_style(self, project_id, style: dict, url: str) -> None:
        row = self.db.query(StylePreset).filter(StylePreset.project_id == project_id).first()
        if not row:
            row = StylePreset(project_id=project_id)
            self.db.add(row)
        row.style_tags = style.get("style_tags", [])
        row.free_text = style.get("prompt", "")
        row.plate_image_url = url
        row.negative_prompt = style.get("negative_prompt", "")
