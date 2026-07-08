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


def facts_from_state_changes(scene_number: int, state_changes: list,
                             characters: list) -> list[dict]:
    """Pure: the set dresser's prop-state changes become graph Facts, known
    by everyone present in the scene."""
    facts = []
    for i, ch in enumerate(state_changes or []):
        state = ch.get("state") if isinstance(ch, dict) else None
        if not state:
            continue
        facts.append({
            "fact_id": f"s{scene_number}-state{i}",
            "text": str(state),
            "scene_number": scene_number,
            "category": "prop_state",
            "known_by": [str(c) for c in (characters or []) if c],
        })
    return facts


def sync_scene_facts(project_id: str, scene_number: int, state_changes: list,
                     characters: list) -> int:
    """WRITE side of narrative memory: persist a scene's established facts."""
    try:
        facts = facts_from_state_changes(scene_number, state_changes, characters)
        if not facts:
            return 0
        ng = NarrativeGraph(project_id=project_id)
        for f in facts:
            ng.record_fact(**f)
        return len(facts)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Neo4j fact sync skipped: {e}")
        return 0


def recall_facts_before_scene(project_id: str, scene_number: int) -> list[str]:
    """READ side: everything the story has established before this scene —
    consulted by the Director while staging it."""
    try:
        ng = NarrativeGraph(project_id=project_id)
        return ng.get_facts_before_scene(scene_number)[:6]
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Neo4j recall skipped: {e}")
        return []
