import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.script import Script
from app.models.character import Character
from app.schemas.character import CharacterCreate, CharacterResponse
from app.services.character_extractor import CharacterExtractor
from app.services.mbti_inferrer import MBTIInferrer

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

    extractor = CharacterExtractor()
    characters_data = await extractor.extract(script.structured_json)

    inferrer = MBTIInferrer()
    created = []

    # Replace any previously extracted characters for this project.
    db.query(Character).filter(Character.project_id == script.project_id).delete()

    for char_data in characters_data:
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
