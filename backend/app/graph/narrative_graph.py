from app.graph.neo4j_client import Neo4jClient, facts_before_scene_query


class NarrativeGraph:
    def __init__(self, project_id: str, client: Neo4jClient | None = None):
        self.project_id = project_id
        self.client = client or Neo4jClient()

    # ── Writes ────────────────────────────────────────────────
    def register_character(self, name: str, role: str, mbti: str = "", visual_description: str = "") -> None:
        self.client.write(
            "MERGE (c:Character {project_id:$pid, name:$name}) "
            "SET c.role=$role, c.mbti=$mbti, c.visual_description=$vd",
            {"pid": self.project_id, "name": name, "role": role, "mbti": mbti, "vd": visual_description},
        )

    def register_scene(self, number: int, heading: str = "", scene_uuid: str | None = None) -> None:
        self.client.write(
            "MERGE (s:Scene {project_id:$pid, number:$number}) SET s.heading=$heading, s.scene_uuid=$scene_uuid",
            {"pid": self.project_id, "number": number, "heading": heading, "scene_uuid": scene_uuid},
        )

    def link_appears_in(self, character: str, scene_number: int) -> None:
        self.client.write(
            "MATCH (c:Character {project_id:$pid, name:$name}) "
            "MATCH (s:Scene {project_id:$pid, number:$num}) "
            "MERGE (c)-[:APPEARS_IN]->(s)",
            {"pid": self.project_id, "name": character, "num": scene_number},
        )

    def record_fact(self, fact_id: str, text: str, scene_number: int, category: str,
                    known_by: list[str] | None = None) -> None:
        self.client.write(
            "MERGE (f:Fact {project_id:$pid, fact_id:$fid}) "
            "SET f.text=$text, f.category=$cat "
            "WITH f MATCH (s:Scene {project_id:$pid, number:$num}) "
            "MERGE (f)-[:ESTABLISHED_IN]->(s)",
            {"pid": self.project_id, "fid": fact_id, "text": text, "cat": category, "num": scene_number},
        )
        for name in (known_by or []):
            self.client.write(
                "MATCH (c:Character {project_id:$pid, name:$name}) "
                "MATCH (f:Fact {project_id:$pid, fact_id:$fid}) MERGE (c)-[:KNOWS_ABOUT]->(f)",
                {"pid": self.project_id, "name": name, "fid": fact_id},
            )

    def record_contradiction(self, fact_a: str, fact_b: str) -> None:
        self.client.write(
            "MATCH (a:Fact {project_id:$pid, fact_id:$a}) "
            "MATCH (b:Fact {project_id:$pid, fact_id:$b}) MERGE (a)-[:CONTRADICTS]->(b)",
            {"pid": self.project_id, "a": fact_a, "b": fact_b},
        )

    def record_relationship(self, from_char: str, to_char: str, rel_type: str, strength: int) -> None:
        self.client.write(
            "MATCH (a:Character {project_id:$pid, name:$a}) "
            "MATCH (b:Character {project_id:$pid, name:$b}) "
            "MERGE (a)-[r:RELATES_TO {type:$t}]->(b) SET r.strength=$s",
            {"pid": self.project_id, "a": from_char, "b": to_char, "t": rel_type, "s": strength},
        )

    def record_agent_decision(self, agent: str, rationale: str, confidence: float) -> None:
        """Every crew verdict lands in the graph — the reporter mirrors here."""
        self.client.write(
            "MERGE (a:Agent {project_id:$pid, name:$agent}) "
            "CREATE (d:Decision {project_id:$pid, rationale:$r, confidence:$c, at:timestamp()}) "
            "MERGE (a)-[:DECIDED]->(d)",
            {"pid": self.project_id, "agent": agent,
             "r": (rationale or "")[:300], "c": float(confidence or 0.0)},
        )

    # ── Reads (real Cypher) ───────────────────────────────────
    def get_facts_before_scene(self, scene_number: int, character: str | None = None) -> list[str]:
        cypher, params = facts_before_scene_query(self.project_id, scene_number, character)
        return [row["fact"] for row in self.client.run(cypher, params)]

    def get_character_context(self, character: str, scene_number: int) -> str:
        rows = self.client.run(
            "MATCH (c:Character {project_id:$pid, name:$name}) "
            "OPTIONAL MATCH (c)-[:KNOWS_ABOUT]->(f:Fact)-[:ESTABLISHED_IN]->(s:Scene) "
            "WHERE s.number <= $num "
            "RETURN c.visual_description AS vd, collect(DISTINCT f.text) AS knows",
            {"pid": self.project_id, "name": character, "num": scene_number},
        )
        if not rows:
            return ""
        vd = rows[0].get("vd") or ""
        knows = [k for k in (rows[0].get("knows") or []) if k]
        ctx = vd
        if knows:
            ctx += " Knows: " + "; ".join(knows[:5]) + "."
        return ctx.strip()

    def check_contradiction(self, proposed_fact: str, scene_number: int) -> bool:
        existing = self.get_facts_before_scene(scene_number)
        pl = proposed_fact.lower()
        return any(f.lower() in pl or pl in f.lower() for f in existing)
