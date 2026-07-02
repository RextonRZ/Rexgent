import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import get_settings
from app.models.script import Script
from app.models.character import Character
from app.schemas.character import CharacterCreate, CharacterResponse
from app.services.character_extractor import CharacterExtractor
from app.services.mbti_inferrer import MBTIInferrer
from app.services.face_embedder import FaceEmbedder
from app.services.appearance_generator import AppearanceGenerator
from app.services.oss_manager import OSSManager
from app.graph.sync import sync_characters

router = APIRouter(prefix="/api/characters", tags=["characters"])


@router.post("/extract")
async def extract_characters(request: dict, db: Session = Depends(get_db)):
    # Accept either an explicit script_id or a project_id (resolves latest script).
    script_id = request.get("script_id")
    project_id = request.get("project_id")

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

    if not script or not script.structured_json:
        raise HTTPException(status_code=404, detail="Script not found or not structured")

    # MBTI is a "for fun" extra — off by default so it does not burn Qwen-Max tokens.
    infer_mbti = bool(request.get("infer_mbti", False))

    extractor = CharacterExtractor()
    characters_data = await extractor.extract(script.structured_json)

    inferrer = MBTIInferrer() if infer_mbti else None
    created = []

    # Replace any previously extracted characters for this project.
    db.query(Character).filter(Character.project_id == script.project_id).delete()

    for char_data in characters_data:
        mbti_result = {}
        if inferrer is not None:
            mbti_result = await inferrer.infer(
                character_name=char_data.get("name", "Unknown"),
                dialogue_samples=char_data.get("key_dialogue_samples", []),
                personality_summary=char_data.get("personality_summary", ""),
                actions_summary=", ".join(char_data.get("relationships", [])),
            )

        character = Character(
            project_id=script.project_id,
            name=char_data.get("name", "Unknown"),
            role=char_data.get("role"),
            gender=char_data.get("gender"),
            estimated_age=char_data.get("estimated_age"),
            physical_description=char_data.get("physical_description"),
            personality_summary=char_data.get("personality_summary"),
            mbti=mbti_result.get("mbti_type"),
            mbti_confidence=mbti_result.get("confidence"),
            speech_pattern=char_data.get("speech_pattern"),
            emotional_arc=char_data.get("emotional_arc"),
        )
        db.add(character)
        created.append(character)

    db.commit()
    for c in created:
        db.refresh(c)

    sync_characters(str(script.project_id), created, script.structured_json)

    return {"characters": [CharacterResponse.model_validate(c) for c in created]}


@router.post("/create", response_model=CharacterResponse)
async def create_character(request: CharacterCreate, db: Session = Depends(get_db)):
    character = Character(**request.model_dump())
    db.add(character)
    db.commit()
    db.refresh(character)
    return character


@router.get("/project/{project_id}")
async def list_characters(project_id: str, db: Session = Depends(get_db)):
    characters = db.query(Character).filter(Character.project_id == uuid.UUID(project_id)).all()
    return {"characters": [CharacterResponse.model_validate(c) for c in characters]}


@router.get("/{character_id}", response_model=CharacterResponse)
async def get_character(character_id: str, db: Session = Depends(get_db)):
    character = db.query(Character).filter(Character.id == uuid.UUID(character_id)).first()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return character


@router.patch("/{character_id}", response_model=CharacterResponse)
async def update_character(character_id: str, updates: dict, db: Session = Depends(get_db)):
    character = db.query(Character).filter(Character.id == uuid.UUID(character_id)).first()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    allowed = {
        "name", "role", "gender", "estimated_age", "physical_description",
        "personality_summary", "mbti", "mbti_confidence", "speech_pattern",
        "emotional_arc", "visual_description", "video_prompt_fragment", "face_keywords",
    }
    for key, value in updates.items():
        if key in allowed:
            setattr(character, key, value)
    db.commit()
    db.refresh(character)
    return character


@router.post("/{character_id}/face", response_model=CharacterResponse)
async def upload_face(
    character_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    character = db.query(Character).filter(Character.id == uuid.UUID(character_id)).first()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    content = await file.read()
    oss = OSSManager(get_settings())
    # unique filename so a re-uploaded face gets a new url (else the browser caches
    # the old face at the same deterministic url)
    oss_key = oss.get_project_path(
        str(character.project_id), f"characters/{character_id}",
        f"reference_{uuid.uuid4().hex[:8]}.jpg",
    )
    image_url = oss.upload_bytes(content, oss_key, content_type="image/jpeg")

    embedder = FaceEmbedder()
    result = await embedder.extract(image_bytes=content, image_url=image_url)
    description = result["description"]

    character.reference_image_url = image_url
    character.face_vector = result["vector"]            # real ArcFace vector (or None)
    character.face_embedding = description              # Qwen-VL text description
    character.face_keywords = description.get("embedding_keywords", [])
    character.visual_description = description.get("face_description", "")
    db.commit()
    db.refresh(character)

    return character


@router.post("/{character_id}/generate-appearance")
async def generate_appearance(character_id: str, db: Session = Depends(get_db)):
    character = db.query(Character).filter(Character.id == uuid.UUID(character_id)).first()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    generator = AppearanceGenerator()
    appearance = await generator.generate(
        character_name=character.name,
        role=character.role or "SUPPORTING",
        personality=character.personality_summary or "",
        mbti=character.mbti or "",
        physical_desc=character.physical_description or "",
    )

    character.visual_description = appearance.get("full_description", "")
    character.video_prompt_fragment = appearance.get("video_prompt_fragment", "")
    character.face_keywords = appearance.get("face_keywords", [])
    db.commit()
    db.refresh(character)

    return {
        "character": CharacterResponse.model_validate(character),
        "appearance": appearance,
    }
