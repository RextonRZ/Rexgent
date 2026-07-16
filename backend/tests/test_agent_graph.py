import pytest
import app.agent.graph as agraph
from app.agent.graph import (build_pipeline_graph, route_after_judge,
                             build_revision_notes, rewrite_regressed)


def test_revision_notes_include_the_previous_draft():
    # the reviser was rewriting blind: premise + critique bullets, never the
    # draft it was told to fix — "keep what worked" without seeing what worked
    j = {"blocking_issues": ["hook is weak"], "top_weaknesses": ["flat ending"]}
    n = build_revision_notes(j, "INT. CABIN - NIGHT\nANNA: We need to talk.")
    assert "hook is weak" in n
    assert "flat ending" in n
    assert "PREVIOUS DRAFT" in n
    assert "We need to talk." in n


def test_revision_notes_without_draft_still_nonempty():
    n = build_revision_notes({}, None)
    assert "REVISION PASS" in n
    assert "PREVIOUS DRAFT" not in n


def test_rewrite_regressed_detects_a_worse_rewrite():
    # the 09:33 drama: draft 6.3 -> rewrite 5.3; the rewrite must not ship
    assert rewrite_regressed({"overall": 6.3}, {"overall": 5.3}) is True
    assert rewrite_regressed({"overall": 6.1}, {"overall": 8.3}) is False
    assert rewrite_regressed({"overall": 6.0}, {"overall": 6.0}) is False
    assert rewrite_regressed(None, {"overall": 5.0}) is False
    assert rewrite_regressed({"overall": "bad"}, {"overall": 5.0}) is False


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


def test_casting_wires_straight_into_budget():
    # TTS synthesis was removed, so the no-op audio node is gone: casting now
    # flows directly into budget.
    from app.agent.graph import build_pipeline_graph
    g = build_pipeline_graph(db=None)
    graph = g.get_graph()
    assert "audio" not in set(graph.nodes.keys())
    edges = {(e.source, e.target) for e in graph.edges}
    assert ("casting", "budget") in edges


def test_clarify_node_in_graph():
    from app.agent.graph import build_pipeline_graph
    g = build_pipeline_graph(db=None)
    assert "clarify" in set(g.get_graph().nodes.keys())


def test_judge_gate_branches():
    assert route_after_judge({"judgement": {"recommendation": "REVISE_FIRST"}, "revise_count": 0}) == "revise"
    # Full Auto rolls on to casting; otherwise the approved script ENDS the
    # run at its checkpoint — later stages wait for the user to continue.
    assert route_after_judge({"judgement": {"recommendation": "PROCEED"},
                              "dispatch_video": True}) == "extract_characters"
    assert route_after_judge({"judgement": {"recommendation": "PROCEED"}}) == "END"


def test_judge_gate_stops_revising_after_max():
    # Already revised once -> stop revising even if still flagged; where it
    # goes next still depends on Full Auto vs the checkpoint stop.
    assert route_after_judge({"judgement": {"recommendation": "REVISE_FIRST"}, "revise_count": 1,
                              "dispatch_video": True}) == "extract_characters"
    assert route_after_judge({"judgement": {"recommendation": "REVISE_FIRST"},
                              "revise_count": 1}) == "END"


@pytest.mark.asyncio
async def test_graph_runs_structure_db_none():
    # With db=None nodes are passthrough; verifies the graph wiring executes end to end.
    g = build_pipeline_graph(db=None)
    state = await g.ainvoke({
        "project_id": "p1", "premise": "x", "genre": "drama",
        "auto": True, "revise_count": 0,
    })
    assert state["project_id"] == "p1"
