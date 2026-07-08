from app.graph.narrative_graph import NarrativeGraph
from app.graph.sync import facts_from_state_changes


class StubClient:
    def __init__(self):
        self.writes = []

    def write(self, cypher, params):
        self.writes.append((cypher, params))

    def run(self, cypher, params):
        return []


def test_state_changes_become_scene_facts_known_by_the_cast():
    facts = facts_from_state_changes(
        3,
        [{"state": "the blue vase lies shattered", "from_shot": 3},
         {"state": None},  # malformed rows never crash the sync
         "not-a-dict"],
        ["Mei", "Rex"],
    )
    assert len(facts) == 1
    f = facts[0]
    assert f["scene_number"] == 3
    assert f["category"] == "prop_state"
    assert "shattered" in f["text"]
    assert f["known_by"] == ["Mei", "Rex"]


def test_no_state_changes_no_facts():
    assert facts_from_state_changes(1, [], ["Mei"]) == []
    assert facts_from_state_changes(1, None, None) == []


def test_agent_decisions_actually_reach_the_graph():
    # the reporter guards on hasattr — this method existing is what turns the
    # decision mirror from a silent no-op into real writes
    client = StubClient()
    ng = NarrativeGraph("pid-1", client=client)
    assert hasattr(ng, "record_agent_decision")
    ng.record_agent_decision("narrative_judge", "weak hook, revise", 0.7)
    assert len(client.writes) == 1
    cypher, params = client.writes[0]
    assert "Decision" in cypher and "DECIDED" in cypher
    assert params["agent"] == "narrative_judge"
    assert params["c"] == 0.7


def test_record_fact_writes_knowledge_edges():
    client = StubClient()
    ng = NarrativeGraph("pid-1", client=client)
    ng.record_fact("f1", "the letter is hidden", 2, "plot", known_by=["Mei"])
    # one write for the fact, one per knower
    assert len(client.writes) == 2
    assert "ESTABLISHED_IN" in client.writes[0][0]
    assert "KNOWS_ABOUT" in client.writes[1][0]
