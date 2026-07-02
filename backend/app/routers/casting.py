import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.project import Project
from app.models.character import Character
from app.models.costume_variant import CostumeVariant
from app.models.location_plate import LocationPlate
from app.models.style_preset import StylePreset
from app.services.plate_generator import PlateGenerator
from app.services.oss_manager import OSSManager
from app.services.face_embedder import FaceEmbedder
from app.services.qwen_client import QwenClient
from app.config import get_settings

router = APIRouter(prefix="/api/casting", tags=["casting"])


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
                       "description": l.description, "plate_image_url": l.plate_image_url}
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
    if char.reference_image_url:
        prompt = (f"Keep this exact same person and face unchanged. Full-body shot, "
                  f"wearing {v.outfit_description or ''}. neutral background")
    else:
        prompt = f"{char.visual_description or char.name}, full-body shot, wearing {v.outfit_description or ''}. neutral background"
    url, vector = await PlateGenerator().generate_and_store_plate(
        str(char.project_id), "character", f"{char.name}_{v.label}", prompt,
        base_image_url=char.reference_image_url)
    v.plate_image_url, v.face_vector, v.plate_status = url, vector, "ai_generated"
    # never clobber an uploaded face — only seed identity if none exists yet
    if v.is_default and not char.reference_image_url:
        char.reference_image_url, char.face_vector = url, vector
    db.commit()
    return {"plate_image_url": url}


@router.post("/variant/{variant_id}/override")
async def override_variant(variant_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    v = db.query(CostumeVariant).filter(CostumeVariant.id == uuid.UUID(variant_id)).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")
    char = db.query(Character).filter(Character.id == v.character_id).first()
    content = await file.read()
    oss = OSSManager(get_settings())
    key = oss.get_project_path(str(char.project_id), "plates/character", f"{char.name}_{v.label}_override.jpg")
    url = oss.upload_bytes(content, key, content_type="image/jpeg")
    result = await FaceEmbedder().extract(image_bytes=content, image_url=url)
    v.plate_image_url, v.face_vector, v.plate_status = url, result.get("vector"), "user_override"
    if v.is_default:
        char.reference_image_url, char.face_vector = url, result.get("vector")
    db.commit()
    return {"plate_image_url": url}


@router.post("/character/{character_id}/voice/design")
def set_voice(character_id: str, voice: str = "Cherry", db: Session = Depends(get_db)):
    """Pick a preset TTS voice (qwen3-tts-flash timbre) for the character."""
    from app.services.voice_catalog import ALL_IDS
    c = db.query(Character).filter(Character.id == uuid.UUID(character_id)).first()
    if not c:
        raise HTTPException(status_code=404, detail="Character not found")
    c.voice_id = voice if voice in ALL_IDS else "Cherry"
    c.voice_model, c.voice_source = get_settings().qwen_tts_designed_model, "preset"
    db.commit()
    return {"voice_id": c.voice_id}


@router.post("/character/{character_id}/voice/clone")
async def clone_voice(character_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Clone a custom voice from an uploaded sample (5-20s). Enrols it via
    qwen-voice-enrollment; the character then speaks with the realtime vc model."""
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
    try:
        voice = await QwenClient(settings).enroll_voice(
            content, preferred_name=c.name, content_type=ctype)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Voice enrollment failed: {e}")
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
