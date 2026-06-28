import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.script import Script, Scene
from app.models.character import Character
from app.models.relationship import CharacterRelationship
from app.services.relationship_builder import RelationshipBuilder

router = APIRouter(prefix="/api/graph", tags=["graph"])


def _serialize_rel(r: CharacterRelationship) -> dict:
    return {
        "id": str(r.id),
        "from_char_id": str(r.from_char_id),
        "to_char_id": str(r.to_char_id),
        "rel_type": r.rel_type,
        "strength": r.strength,
        "description": r.description,
        "first_established_scene": r.first_established_scene,
        "evidence_quote": r.evidence_quote,
        "evolution": r.evolution,
        "evolution_description": r.evolution_description,
    }


@router.post("/relationship")
async def build_relationship_graph(request: dict, db: Session = Depends(get_db)):
    project_id = request.get("project_id")
    script_id = request.get("script_id")

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
        raise HTTPException(status_code=404, detail="Script not found")

    characters = db.query(Character).filter(Character.project_id == script.project_id).all()
    if not characters:
        raise HTTPException(status_code=400, detail="No characters — run character extraction first")

    chars_json = [{"name": c.name, "role": c.role} for c in characters]

    builder = RelationshipBuilder()
    relationships = await builder.extract(script.structured_json, chars_json)

    char_map = {c.name.upper(): c for c in characters}

    # Replace existing relationships for this project.
    db.query(CharacterRelationship).filter(
        CharacterRelationship.project_id == script.project_id
    ).delete()

    created = []
    for rel in relationships:
        from_char = char_map.get(str(rel.get("from_character", "")).upper())
        to_char = char_map.get(str(rel.get("to_character", "")).upper())
        if not from_char or not to_char:
            continue

        db_rel = CharacterRelationship(
            project_id=script.project_id,
            from_char_id=from_char.id,
            to_char_id=to_char.id,
            rel_type=rel.get("relationship_type", "COLLEAGUE"),
            strength=rel.get("strength", 5),
            description=rel.get("description"),
            first_established_scene=rel.get("first_established_scene"),
            evidence_quote=rel.get("evidence_quote"),
            evolution=rel.get("evolution", "STATIC"),
            evolution_description=rel.get("evolution_description"),
        )
        db.add(db_rel)
        created.append(db_rel)

    db.commit()
    for r in created:
        db.refresh(r)

    return {"relationships": [_serialize_rel(r) for r in created]}


@router.get("/{project_id}")
async def get_graphs(project_id: str, db: Session = Depends(get_db)):
    pid = uuid.UUID(project_id)
    characters = db.query(Character).filter(Character.project_id == pid).all()
    relationships = (
        db.query(CharacterRelationship)
        .filter(CharacterRelationship.project_id == pid)
        .all()
    )

    # Scene graph data: scenes + which characters appear in each.
    script = (
        db.query(Script)
        .filter(Script.project_id == pid)
        .order_by(Script.created_at.desc())
        .first()
    )
    scenes = []
    if script:
        scene_rows = db.query(Scene).filter(Scene.script_id == script.id).order_by(Scene.number).all()
        scenes = [
            {
                "number": s.number,
                "heading": s.heading,
                "characters": s.characters_json or [],
            }
            for s in scene_rows
        ]

    return {
        "characters": [
            {"id": str(c.id), "name": c.name, "role": c.role} for c in characters
        ],
        "relationships": [_serialize_rel(r) for r in relationships],
        "scenes": scenes,
    }
