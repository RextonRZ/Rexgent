"""Best-effort Neo4j population. Failures here never break the core (Postgres) flow."""
import logging
from app.graph.narrative_graph import NarrativeGraph

logger = logging.getLogger(__name__)


def sync_scenes(project_id: str, structured: dict, scene_uuids: dict | None = None) -> None:
    try:
        ng = NarrativeGraph(project_id=project_id)
        scene_uuids = scene_uuids or {}
        for sc in structured.get("scenes", []):
            number = sc.get("scene_number", 0)
            ng.register_scene(
                number=number,
                heading=sc.get("heading", ""),
                scene_uuid=scene_uuids.get(number),
            )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Neo4j scene sync skipped: {e}")


def sync_characters(project_id: str, characters: list, structured: dict) -> None:
    try:
        ng = NarrativeGraph(project_id=project_id)
        for c in characters:
            ng.register_character(
                name=c.name, role=c.role or "", mbti=c.mbti or "",
                visual_description=c.visual_description or "",
            )
        for sc in (structured or {}).get("scenes", []):
            for name in sc.get("characters_present", []):
                ng.link_appears_in(character=name, scene_number=sc.get("scene_number", 0))
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Neo4j character sync skipped: {e}")


def sync_relationships(project_id: str, relationships: list, name_by_id: dict) -> None:
    try:
        ng = NarrativeGraph(project_id=project_id)
        for r in relationships:
            ng.record_relationship(
                from_char=name_by_id.get(str(r.from_char_id), ""),
                to_char=name_by_id.get(str(r.to_char_id), ""),
                rel_type=r.rel_type, strength=r.strength or 5,
            )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Neo4j relationship sync skipped: {e}")
