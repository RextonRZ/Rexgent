import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.project import Project
from app.models.character import Character
from app.models.costume_variant import CostumeVariant
from app.models.location_plate import LocationPlate
from app.models.style_preset import StylePreset
from app.services.plate_generator import (PlateGenerator, character_plate_prompt,
                                          subject_descriptor, CHAR_PLATE_NEGATIVE,
                                          char_plate_negative)
from app.services.oss_manager import OSSManager
from app.services.face_embedder import FaceEmbedder
from app.services.qwen_client import QwenClient
from app.config import get_settings

from app.deps import get_current_user

router = APIRouter(prefix="/api/casting", tags=["casting"],
                   # every pipeline endpoint requires a signed-in user
                   dependencies=[Depends(get_current_user)])


def _to_wav(data: bytes) -> bytes:
    """Transcode arbitrary audio (e.g. browser webm/opus) to 16kHz mono WAV via
    ffmpeg. Falls back to the original bytes if ffmpeg is unavailable."""
    import subprocess
    try:
        proc = subprocess.run(
            ["ffmpeg", "-i", "pipe:0", "-f", "wav", "-ar", "16000", "-ac", "1", "pipe:1"],
            input=data, capture_output=True, timeout=60,
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout
    except Exception:  # noqa: BLE001
        pass
    return data


def allocate_and_generate(db: Session, project_id: str) -> str:
    """Resume the pipeline after casting review: budget then dispatch generation."""
    from app.agent.pipeline_ops import allocate_budget_op, dispatch_generation_op
    from app.models.script import Script, Scene
    from app.models.shot import Shot
    script = (db.query(Script).filter(Script.project_id == uuid.UUID(project_id))
              .order_by(Script.created_at.desc()).first())
    scene_ids = [s.id for s in db.query(Scene).filter(Scene.script_id == script.id).all()]
    shots = db.query(Shot).filter(Shot.scene_id.in_(scene_ids)).all()
    shot_dicts = [{"shot_id": str(s.id), "emotional_beat": s.emotional_beat,
                   "estimated_duration_seconds": s.estimated_duration_seconds} for s in shots]
    allocate_budget_op(db, project_id, shot_dicts)
    return dispatch_generation_op(db, project_id)


@router.get("/voices")
def list_voices():
    """The preset TTS voice catalog (id, gender, description) for the picker."""
    from app.services.voice_catalog import VOICES
    return VOICES


@router.get("/{project_id}")
def get_bible(project_id: str, db: Session = Depends(get_db)):
    pid = uuid.UUID(project_id)
    chars = db.query(Character).filter(Character.project_id == pid).all()
    project = db.query(Project).filter(Project.id == pid).first()
    return {
        "auto_approve_casting": (project.auto_approve_casting if project else False),
        "characters": [{"id": str(c.id), "name": c.name,
            "voice_id": c.voice_id, "voice_source": c.voice_source,
            "variants": [{"id": str(v.id), "label": v.label, "outfit_description": v.outfit_description,
                          "plate_image_url": v.plate_image_url, "is_default": v.is_default,
                          "plate_status": v.plate_status}
                         for v in db.query(CostumeVariant).filter(CostumeVariant.character_id == c.id).all()]}
            for c in chars],
        "locations": [{"id": str(l.id), "location_key": l.location_key,
                       "description": l.description, "plate_image_url": l.plate_image_url,
                       "scene_numbers": l.scene_numbers or []}
                      for l in db.query(LocationPlate).filter(LocationPlate.project_id == pid).all()],
        "style": (lambda s: {"style_tags": s.style_tags, "plate_image_url": s.plate_image_url} if s else None)(
                  db.query(StylePreset).filter(StylePreset.project_id == pid).first()),
    }


@router.post("/{project_id}/approve")
def approve_casting(project_id: str, db: Session = Depends(get_db)):
    if not db.query(Project).filter(Project.id == uuid.UUID(project_id)).first():
        raise HTTPException(status_code=404, detail="Project not found")
    return {"job_id": allocate_and_generate(db, project_id)}


@router.post("/{project_id}/run")
def run_casting(project_id: str, db: Session = Depends(get_db)):
    if not db.query(Project).filter(Project.id == uuid.UUID(project_id)).first():
        raise HTTPException(status_code=404, detail="Project not found")
    # announce BEFORE dispatching: the worker takes seconds to pick the job
    # up and its first LLM call takes longer — without this the click felt
    # dead for half a minute
    from app.websocket.emitter import emit
    emit("stage:progress", {"stage": "casting", "status": "started",
         "agent": "Casting Director", "label": "Casting the production bible"},
         project_id)
    from app.workers.casting_worker import run_casting_job
    run_casting_job.delay(project_id)
    return {"status": "started"}


@router.patch("/{project_id}/auto-approve")
def set_auto_approve(project_id: str, enabled: bool, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == uuid.UUID(project_id)).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project.auto_approve_casting = enabled
    db.commit()
    return {"auto_approve_casting": enabled}


@router.post("/variant/{variant_id}/regenerate")
async def regenerate_variant(variant_id: str, db: Session = Depends(get_db)):
    v = db.query(CostumeVariant).filter(CostumeVariant.id == uuid.UUID(variant_id)).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")
    char = db.query(Character).filter(Character.id == v.character_id).first()
    prompt = _char_plate_prompt(char, v.outfit_description or "")
    # narrate over the stage channel too — the chat bubble and dock listen to
    # stage:progress, tool events alone light only the crew graph
    from app.websocket.emitter import emit
    pid = str(char.project_id)
    emit("stage:progress", {"stage": "casting", "status": "started",
         "agent": "Casting Director",
         "label": f"Re-rendering {char.name} ({v.label})"}, pid)
    from app.websocket.tool_events import tool_run
    with tool_run(pid, "characters", "generate_plates", "Casting") as tb:
        url, vector = await PlateGenerator().generate_and_store_plate(
            str(char.project_id), "character", f"{char.name}_{v.label}", prompt,
            negative_prompt=char_plate_negative(
                char.visual_description, char.physical_description,
                char.video_prompt_fragment, v.outfit_description),
            base_image_url=char.reference_image_url, prompt_extend=False,
            match_vector=char.face_vector if char.reference_image_url else None)
        tb["artifact"] = f"{char.name} {v.label} replated"
    v.plate_image_url, v.face_vector, v.plate_status = url, vector, "ai_generated"
    # never clobber an uploaded face — only seed identity if none exists yet
    if v.is_default and not char.reference_image_url:
        char.reference_image_url, char.face_vector = url, vector
    db.commit()
    emit("stage:progress", {"stage": "casting", "status": "completed",
         "agent": "Casting Director",
         "label": f"{char.name} ({v.label}) replated"}, pid)
    return {"plate_image_url": url}


@router.post("/variant/{variant_id}/override")
async def override_variant(variant_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    v = db.query(CostumeVariant).filter(CostumeVariant.id == uuid.UUID(variant_id)).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")
    char = db.query(Character).filter(Character.id == v.character_id).first()
    content = await file.read()
    oss = OSSManager(get_settings())
    key = oss.get_project_path(str(char.project_id), "plates/character",
                               f"{char.name}_{v.label}_override_{uuid.uuid4().hex[:8]}.jpg")
    url = oss.upload_bytes(content, key, content_type="image/jpeg")
    result = await FaceEmbedder().extract(image_bytes=content, image_url=url)
    v.plate_image_url, v.face_vector, v.plate_status = url, result.get("vector"), "user_override"
    if v.is_default:
        char.reference_image_url, char.face_vector = url, result.get("vector")
    db.commit()
    return {"plate_image_url": url}


def _char_plate_prompt(char, outfit: str) -> str:
    subject = subject_descriptor(char.gender, char.estimated_age,
                                 char.physical_description or char.visual_description)
    return character_plate_prompt(bool(char.reference_image_url), subject, outfit)


_OUTFIT_READ_PROMPT = (
    "You are a costume designer. Describe ONLY the outfit visible in this image "
    "in precise, render-ready detail: every garment, its color, material, pattern, "
    "fit and layering, plus ALL headwear (caps, hats, hoods, beanies), eyewear, "
    "accessories and footwear if visible. COMPLETELY IGNORE "
    "whoever is wearing it: no face, hair, age, gender, body or identity details "
    "of any person may appear in your answer. "
    'Return ONLY JSON: {"outfit_description": "..."}'
)


@router.post("/variant/{variant_id}/outfit")
async def swap_variant_outfit(variant_id: str, file: UploadFile = File(...),
                              db: Session = Depends(get_db)):
    """Re-dress a costume variant from ANY outfit photo. A vision pass reads
    just the clothing (whoever wears it in the photo is deliberately ignored),
    then the plate re-renders with the CHARACTER's own locked face wearing that
    outfit — verified against the face reference like every other plate."""
    v = db.query(CostumeVariant).filter(CostumeVariant.id == uuid.UUID(variant_id)).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")
    char = db.query(Character).filter(Character.id == v.character_id).first()
    content = await file.read()

    import base64
    from app.services.usage_tracker import track_project
    from app.websocket.emitter import emit
    from app.websocket.tool_events import tool_run
    pid = str(char.project_id)
    emit("stage:progress", {"stage": "casting", "status": "started",
         "agent": "Casting Director",
         "label": f"Reading the outfit from your photo for {char.name}"}, pid)
    # normalize the upload: phone photos arrive huge and in any format (HEIC,
    # webp, PNG) — re-encode to a bounded JPEG so the vision call never chokes
    # on payload size or an unsupported container
    try:
        import io as _io
        from PIL import Image as _Image
        img = _Image.open(_io.BytesIO(content)).convert("RGB")
        img.thumbnail((1280, 1280))
        buf = _io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        content = buf.getvalue()
    except Exception:
        emit("stage:progress", {"stage": "casting", "status": "failed",
             "agent": "Casting Director",
             "label": "That file does not read as an image"}, pid)
        raise HTTPException(status_code=422,
                            detail="That file does not read as an image. Upload a JPG or PNG photo of the outfit.")
    b64 = base64.b64encode(content).decode()
    qwen = QwenClient(get_settings())
    try:
        with track_project(char.project_id, db):
            with tool_run(pid, "characters", "generate_plates", "Casting") as tb:
                vl = await qwen.chat_vision_json(
                    messages=[{"role": "user", "content": [
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                        {"type": "text", "text": _OUTFIT_READ_PROMPT},
                    ]}],
                    task="casting")
                outfit = (vl or {}).get("outfit_description") if isinstance(vl, dict) else None
                if not (outfit or "").strip():
                    raise HTTPException(
                        status_code=422,
                        detail="Could not read an outfit from that image. Try a clearer photo of the clothing.")
                v.outfit_description = outfit
                emit("stage:progress", {"stage": "casting", "status": "update",
                     "agent": "Casting Director",
                     "label": f"Re-dressing {char.name} ({v.label}) in the new outfit"}, pid)
                prompt = _char_plate_prompt(char, outfit)
                url, vector = await PlateGenerator(db).generate_and_store_plate(
                    str(char.project_id), "character", f"{char.name}_{v.label}", prompt,
                    negative_prompt=char_plate_negative(
                        char.visual_description, char.physical_description,
                        char.video_prompt_fragment, outfit),
                    base_image_url=char.reference_image_url, prompt_extend=False,
                    match_vector=char.face_vector if char.reference_image_url else None)
                tb["artifact"] = f"{char.name} {v.label} re-dressed"
    except HTTPException as e:
        # close the bubble honestly — an error must never leave it spinning
        emit("stage:progress", {"stage": "casting", "status": "failed",
             "agent": "Casting Director", "label": str(e.detail)[:120]}, pid)
        raise
    except Exception as e:  # noqa: BLE001
        # surface the REAL reason — a bare 500 taught the user nothing
        import logging
        logging.getLogger(__name__).exception("outfit swap failed for %s", char.name)
        reason = f"{type(e).__name__}: {str(e)[:140]}"
        emit("stage:progress", {"stage": "casting", "status": "failed",
             "agent": "Casting Director",
             "label": f"Outfit swap failed for {char.name}: {reason}"}, pid)
        raise HTTPException(status_code=502, detail=f"Outfit swap failed: {reason}")
    emit("stage:progress", {"stage": "casting", "status": "completed",
         "agent": "Casting Director",
         "label": f"{char.name} re-dressed, plate ready"}, pid)
    v.plate_image_url, v.face_vector, v.plate_status = url, vector, "ai_generated"
    # never clobber an uploaded face — only seed identity if none exists yet
    if v.is_default and not char.reference_image_url:
        char.reference_image_url, char.face_vector = url, vector
    db.commit()
    return {"plate_image_url": url, "outfit_description": outfit}


@router.post("/character/{character_id}/plates")
async def generate_character_plates(character_id: str, db: Session = Depends(get_db)):
    """Generate (or regenerate) one character's costume plates on their CURRENT face.
    - No face set  -> text-to-image invents a face and seeds it as the identity.
    - Face set     -> plates are image-edited onto that exact face.
    Call it again after changing the face to re-match. Also assigns a voice if none."""
    from app.services.casting_director import assign_voice
    c = db.query(Character).filter(Character.id == uuid.UUID(character_id)).first()
    if not c:
        raise HTTPException(status_code=404, detail="Character not found")
    project_id = str(c.project_id)
    variants = (db.query(CostumeVariant).filter(CostumeVariant.character_id == c.id)
                .order_by(CostumeVariant.is_default.desc()).all())
    if not variants:
        v = CostumeVariant(character_id=c.id, label="default",
                           outfit_description="",
                           is_default=True, plate_status="ai_pending", scene_numbers=[])
        db.add(v)
        db.flush()
        variants = [v]

    from app.websocket.emitter import emit
    emit("stage:progress", {"stage": "casting", "status": "started",
         "agent": "Casting Director",
         "label": f"Casting {c.name}'s plates"}, project_id)
    from app.websocket.tool_events import tool_event
    tool_event(project_id, "characters", "generate_plates", "started",
               agent="Casting", total=len(variants))
    # no face uploaded must never block generation later — write a look
    if not (c.visual_description or "").strip() or not (c.video_prompt_fragment or "").strip():
        try:
            from app.services.appearance_generator import AppearanceGenerator
            from app.services.usage_tracker import track_project
            with track_project(project_id, db):
                look = await AppearanceGenerator().generate(
                    character_name=c.name, role=c.role or "SUPPORTING",
                    personality=c.personality_summary or "",
                    mbti=getattr(c, "mbti", "") or "",
                    physical_desc=c.physical_description or "")
            c.visual_description = (c.visual_description or "").strip() or look.get("full_description", "")
            c.video_prompt_fragment = (c.video_prompt_fragment or "").strip() or look.get("video_prompt_fragment", "")
        except Exception:  # noqa: BLE001
            pass
    pg = PlateGenerator(db)
    for v in variants:
        prompt = _char_plate_prompt(c, v.outfit_description or "")
        url, vector = await pg.generate_and_store_plate(
            project_id, "character", f"{c.name}_{v.label}", prompt,
            negative_prompt=char_plate_negative(
                c.visual_description, c.physical_description,
                c.video_prompt_fragment, v.outfit_description),
            base_image_url=c.reference_image_url, prompt_extend=False,
            match_vector=c.face_vector if c.reference_image_url else None)
        v.plate_image_url, v.face_vector, v.plate_status = url, vector, "ai_generated"
        # seed identity from the default plate only when no face exists yet
        if v.is_default and not c.reference_image_url:
            c.reference_image_url, c.face_vector, c.plate_status = url, vector, "ai_generated"
    tool_event(project_id, "characters", "generate_plates", "succeeded",
               agent="Casting", artifact=f"{len(variants)} plates on {c.name}")
    if not c.voice_id:
        assign_voice(c, 0)
    db.commit()
    emit("stage:progress", {"stage": "casting", "status": "completed",
         "agent": "Casting Director",
         "label": f"{c.name}: {len(variants)} plate(s) ready"}, project_id)
    return {"variants": [{"id": str(v.id), "label": v.label,
                          "plate_image_url": v.plate_image_url,
                          "plate_status": v.plate_status} for v in variants],
            "voice_id": c.voice_id, "voice_source": c.voice_source,
            "reference_image_url": c.reference_image_url}


@router.post("/character/{character_id}/voice/design")
def set_voice(character_id: str, voice: str = "Cherry", db: Session = Depends(get_db)):
    """Pick a preset TTS voice (qwen3-tts-flash timbre) for the character.
    Existing voice lines are NOT touched here — the export worker compares each
    line's stored voice_id against the character's current voice and re-synthesizes
    only the stale lines (see _ensure_voice_lines)."""
    from app.services.voice_catalog import ALL_IDS
    c = db.query(Character).filter(Character.id == uuid.UUID(character_id)).first()
    if not c:
        raise HTTPException(status_code=404, detail="Character not found")
    c.voice_id = voice if voice in ALL_IDS else "Cherry"
    c.voice_model, c.voice_source = get_settings().qwen_tts_designed_model, "preset"
    db.commit()
    from app.websocket.tool_events import tool_event
    tool_event(str(c.project_id), "characters", "voice_assign", "succeeded",
               agent="Casting", artifact=f"{c.name} → {c.voice_id}")
    return {"voice_id": c.voice_id}


@router.post("/character/{character_id}/voice/clone")
async def clone_voice(character_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Clone a custom voice from an uploaded sample (5-20s). Enrols it via
    qwen-voice-enrollment; the character then speaks with the realtime vc model.
    Existing voice lines are NOT touched — the export worker detects the voice_id
    change and re-synthesizes only this character's lines."""
    settings = get_settings()
    c = db.query(Character).filter(Character.id == uuid.UUID(character_id)).first()
    if not c:
        raise HTTPException(status_code=404, detail="Character not found")
    content = await file.read()
    # Browser mic recordings arrive as webm/ogg — transcode to WAV (best effort) so
    # enrollment gets a format it accepts. File uploads (wav/mp3) pass through.
    ctype = (file.content_type or "audio/wav").lower()
    if "wav" not in ctype and "mpeg" not in ctype and "mp3" not in ctype:
        content = _to_wav(content)
        ctype = "audio/wav"
    # keep the source sample so the clone can be re-enrolled/audited later
    oss = OSSManager(settings)
    sample_key = oss.get_project_path(str(c.project_id), "voice_samples", f"{c.name}_sample.wav")
    sample_url = oss.upload_bytes(content, sample_key, content_type=ctype)
    from app.websocket.tool_events import tool_event
    tool_event(str(c.project_id), "characters", "voice_assign", "started", agent="Casting")
    try:
        voice = await QwenClient(settings).enroll_voice(
            content, preferred_name=c.name, content_type=ctype)
    except Exception as e:  # noqa: BLE001
        tool_event(str(c.project_id), "characters", "voice_assign", "failed",
                   agent="Casting", error=str(e))
        raise HTTPException(status_code=502, detail=f"Voice enrollment failed: {e}")
    tool_event(str(c.project_id), "characters", "voice_assign", "succeeded",
               agent="Casting", artifact=f"{c.name} voice cloned")
    c.voice_id, c.voice_model, c.voice_source = voice, settings.qwen_tts_cloned_model, "cloned"
    c.voice_sample_url = sample_url
    db.commit()
    return {"voice_id": voice, "voice_source": "cloned"}


@router.post("/character/{character_id}/voice/preview")
async def preview_voice(character_id: str, text: str = "Hello, this is my voice.", db: Session = Depends(get_db)):
    c = db.query(Character).filter(Character.id == uuid.UUID(character_id)).first()
    if not c or not c.voice_id:
        raise HTTPException(status_code=404, detail="No voice to preview")
    # cloned voices must preview through their realtime model; presets use flash.
    model = c.voice_model if c.voice_source == "cloned" else None
    audio = await QwenClient(get_settings()).preview_voice(text, c.voice_id, model)
    return Response(content=audio, media_type="audio/wav")
