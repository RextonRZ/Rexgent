import pytest
import app.agent.graph as agraph
from app.agent.graph import build_pipeline_graph, route_after_judge


@pytest.fixture(autouse=True)
def _no_ws(monkeypatch):
    monkeypatch.setattr(agraph, "emit", lambda *a, **k: None)


def test_graph_compiles_with_nodes():
    g = build_pipeline_graph()
    nodes = set(g.get_graph().nodes)
    for n in ["generate_script", "judge", "extract_characters", "storyboard", "budget", "generate_video"]:
        assert n in nodes


def test_casting_node_in_graph():
    from app.agent.graph import build_pipeline_graph
    # Builds without error and includes the casting stage between storyboard and budget.
    g = build_pipeline_graph(db=None)
    node_names = set(g.get_graph().nodes.keys())
    assert "casting" in node_names


def test_judge_gate_branches():
    assert route_after_judge({"judgement": {"recommendation": "REVISE_FIRST"}, "revise_count": 0}) == "revise"
    assert route_after_judge({"judgement": {"recommendation": "PROCEED"}}) == "extract_characters"


def test_judge_gate_stops_revising_after_max():
    # Already revised once -> proceed even if still flagged.
    assert route_after_judge({"judgement": {"recommendation": "REVISE_FIRST"}, "revise_count": 1}) == "extract_characters"


@pytest.mark.asyncio
async def test_graph_runs_structure_db_none():
    # With db=None nodes are passthrough; verifies the graph wiring executes end to end.
    g = build_pipeline_graph(db=None)
    state = await g.ainvoke({
        "project_id": "p1", "premise": "x", "genre": "drama",
        "auto": True, "revise_count": 0,
    })
    assert state["project_id"] == "p1"
