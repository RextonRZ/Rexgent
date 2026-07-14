from app.agents.registry import AGENTS


def test_registry_shape():
    keys = {a["key"] for a in AGENTS}
    assert {"clarification", "narrative_judge", "continuity", "style_casting",
            "budget_allocator"} <= keys
    for a in AGENTS:
        assert {"key", "name", "role", "model"} <= set(a)
