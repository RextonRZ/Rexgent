import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
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
from app.config import get_settings

router = APIRouter(prefix="/api/casting", tags=["casting"])


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


@router.get("/{project_id}")
def get_bible(project_id: str, db: Session = Depends(get_db)):
    pid = uuid.UUID(project_id)
    chars = db.query(Character).filter(Character.project_id == pid).all()
    project = db.query(Project).filter(Project.id == pid).first()
    return {
        "auto_approve_casting": (project.auto_approve_casting if project else False),
        "characters": [{"id": str(c.id), "name": c.name,
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
    prompt = f"{char.visual_description or char.name}, wearing {v.outfit_description or ''}. clean portrait"
    url, vector = await PlateGenerator().generate_and_store_plate(
        str(char.project_id), "character", f"{char.name}_{v.label}", prompt)
    v.plate_image_url, v.face_vector, v.plate_status = url, vector, "ai_generated"
    if v.is_default:
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
