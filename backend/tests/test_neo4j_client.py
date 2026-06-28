from app.graph.neo4j_client import facts_before_scene_query


def test_facts_before_scene_query_has_params():
    cypher, params = facts_before_scene_query(project_id="p1", scene_number=3, character="Yuki")
    assert "Fact" in cypher
    assert "KNOWS_ABOUT" in cypher
    assert params["scene_number"] == 3
    assert params["character"] == "Yuki"


def test_facts_before_scene_no_character():
    cypher, params = facts_before_scene_query(project_id="p1", scene_number=5)
    assert "Fact" in cypher
    assert "KNOWS_ABOUT" not in cypher
    assert "character" not in params
