import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.script import Script, Scene
from app.models.character import Character
from app.models.relationship import CharacterRelationship
from app.services.relationship_builder import RelationshipBuilder
from app.graph.sync import sync_relationships

router = APIRouter(prefix="/api/graph", tags=["graph"])


def _resolve_character(char_map: dict, name) -> object | None:
    """Match an LLM-returned name to a cast member, tolerating cue names.
    Screenplays cue dialogue with short names (REN) while the cast stores
    full names (Ren Ishida) — an exact-only lookup silently drops the edge.
    Tries exact, then first-name/cue-prefix matching (unambiguous only)."""
    key = str(name or "").strip().upper()
    if not key:
        return None
    if key in char_map:
        return char_map[key]
    candidates = [
        c for full, c in char_map.items()
        if full.startswith(key + " ")          # "REN" -> "REN ISHIDA"
        or key.startswith(full + " ")          # "REN ISHIDA" -> "REN"
        or full.split()[0] == key              # first name match
        or key.split()[0] == full              # full given, cast stores cue
    ]
    return candidates[0] if len(candidates) == 1 else None


def _canonical_names(char_map: dict, names) -> list[str]:
    """Rewrite scene cue names to the cast's canonical names so name-keyed
    consumers (story map appears-in links, scene flow) actually connect.
    Unresolved names pass through; duplicates collapse."""
    out = []
    for n in names or []:
        c = _resolve_character(char_map, n)
        out.append(c.name if c else n)
    return list(dict.fromkeys(out))


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
        from_char = _resolve_character(char_map, rel.get("from_character"))
        to_char = _resolve_character(char_map, rel.get("to_character"))
        if not from_char or not to_char or from_char is to_char:
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

    name_by_id = {str(c.id): c.name for c in characters}
    sync_relationships(str(script.project_id), created, name_by_id)

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
    # scene -> location plate image, so graph scene nodes can show the picture
    from app.models.location_plate import LocationPlate
    plate_by_scene: dict[int, str] = {}
    for lp in db.query(LocationPlate).filter(LocationPlate.project_id == pid).all():
        for n in (lp.scene_numbers or []):
            if lp.plate_image_url and n not in plate_by_scene:
                plate_by_scene[n] = lp.plate_image_url

    scenes = []
    if script:
        # scenes store the screenplay's short cue names (REN); the cast stores
        # full names (Ren Ishida) — canonicalize so name-keyed links connect
        char_map = {c.name.upper(): c for c in characters}
        scene_rows = db.query(Scene).filter(Scene.script_id == script.id).order_by(Scene.number).all()
        scenes = [
            {
                "number": s.number,
                "heading": s.heading,
                "characters": _canonical_names(char_map, s.characters_json),
                "image": plate_by_scene.get(s.number),
                "description": s.description,
                "emotional_beat": s.emotional_beat,
            }
            for s in scene_rows
        ]

    return {
        "characters": [
            {
                "id": str(c.id),
                "name": c.name,
                "role": c.role,
                "reference_image_url": c.reference_image_url,
            }
            for c in characters
        ],
        "relationships": [_serialize_rel(r) for r in relationships],
        "scenes": scenes,
    }
