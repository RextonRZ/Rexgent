from neo4j import GraphDatabase
from app.config import get_settings


def facts_before_scene_query(project_id: str, scene_number: int, character: str | None = None):
    """Cypher: facts established before a scene, optionally only those a character knows."""
    if character:
        cypher = (
            "MATCH (f:Fact {project_id:$project_id})-[:ESTABLISHED_IN]->(s:Scene) "
            "WHERE s.number < $scene_number "
            "MATCH (c:Character {project_id:$project_id, name:$character})-[:KNOWS_ABOUT]->(f) "
            "RETURN f.text AS fact, s.number AS scene ORDER BY s.number"
        )
        params = {"project_id": project_id, "scene_number": scene_number, "character": character}
    else:
        cypher = (
            "MATCH (f:Fact {project_id:$project_id})-[:ESTABLISHED_IN]->(s:Scene) "
            "WHERE s.number < $scene_number "
            "RETURN f.text AS fact, s.number AS scene ORDER BY s.number"
        )
        params = {"project_id": project_id, "scene_number": scene_number}
    return cypher, params


class Neo4jClient:
    def __init__(self):
        s = get_settings()
        self._driver = GraphDatabase.driver(
            s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password)
        )

    def close(self):
        self._driver.close()

    def run(self, cypher: str, params: dict | None = None) -> list[dict]:
        with self._driver.session() as session:
            return [r.data() for r in session.run(cypher, params or {})]

    def write(self, cypher: str, params: dict | None = None) -> None:
        with self._driver.session() as session:
            session.execute_write(lambda tx: tx.run(cypher, params or {}))
