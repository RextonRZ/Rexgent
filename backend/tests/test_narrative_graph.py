from unittest.mock import MagicMock
from app.graph.narrative_graph import NarrativeGraph


def test_register_character_writes_node():
    client = MagicMock()
    g = NarrativeGraph(project_id="p1", client=client)
    g.register_character(name="Yuki", role="PROTAGONIST", mbti="INTJ")
    assert client.write.called
    cypher = client.write.call_args[0][0]
    assert "MERGE" in cypher and "Character" in cypher


def test_record_fact_links_to_scene():
    client = MagicMock()
    g = NarrativeGraph(project_id="p1", client=client)
    g.record_fact(fact_id="f1", text="ARIA is an AI", scene_number=2, category="CHARACTER")
    cypher = client.write.call_args[0][0]
    assert "Fact" in cypher and "ESTABLISHED_IN" in cypher


def test_record_fact_links_known_by():
    client = MagicMock()
    g = NarrativeGraph(project_id="p1", client=client)
    g.record_fact(fact_id="f1", text="x", scene_number=1, category="RULE", known_by=["Yuki"])
    # Last write should be the KNOWS_ABOUT link.
    cypher = client.write.call_args[0][0]
    assert "KNOWS_ABOUT" in cypher


def test_register_scene_accepts_uuid():
    client = MagicMock()
    g = NarrativeGraph(project_id="p1", client=client)
    g.register_scene(number=1, heading="INT. CAFE", scene_uuid="abc-123")
    assert client.write.called
    params = client.write.call_args[0][1]
    assert params.get("scene_uuid") == "abc-123"


def test_record_relationship_writes_edge():
    client = MagicMock()
    g = NarrativeGraph(project_id="p1", client=client)
    g.record_relationship(from_char="Yuki", to_char="Aria", rel_type="ALLY", strength=7)
    cypher = client.write.call_args[0][0]
    assert "RELATES_TO" in cypher


def test_get_facts_before_scene_reads():
    client = MagicMock()
    client.run.return_value = [{"fact": "Set in Tokyo", "scene": 1}]
    g = NarrativeGraph(project_id="p1", client=client)
    facts = g.get_facts_before_scene(scene_number=3)
    assert facts == ["Set in Tokyo"]


def test_check_contradiction():
    client = MagicMock()
    client.run.return_value = [{"fact": "ARIA is an AI", "scene": 1}]
    g = NarrativeGraph(project_id="p1", client=client)
    assert g.check_contradiction("ARIA is an AI partner", scene_number=3) is True
    assert g.check_contradiction("Set in 2099 Mars", scene_number=3) is False


def test_get_character_context():
    client = MagicMock()
    client.run.return_value = [{"vd": "young detective", "knows": ["ARIA is an AI"]}]
    g = NarrativeGraph(project_id="p1", client=client)
    ctx = g.get_character_context("Yuki", scene_number=3)
    assert "young detective" in ctx
    assert "ARIA is an AI" in ctx
