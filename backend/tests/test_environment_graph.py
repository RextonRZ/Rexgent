import app.graph.environment_graph as eg
from app.graph.environment_graph import detect_events, location_key


def test_location_key_maps_headings():
    assert location_key("INT. CONCERT HALL - NIGHT") == "concert_hall"
    assert location_key("EXT. CITY STREET - DAY") == "street"
    assert location_key("INT. HOSPITAL ROOM - NIGHT") == "hospital_room"
    assert location_key("INT. SPACESHIP - NIGHT") is None


def test_detect_events_finds_the_collapse():
    text = ("Ryu Sun-jae is performing on stage when he suddenly collapses, "
            "clutching his chest in pain.")
    assert "performer_collapse" in detect_events(text)
    assert detect_events("They chat over coffee.") == []


class FakeGraph:
    """Replays the resolver semantics without Neo4j: highest priority wins."""
    def __init__(self):
        self.writes = []

    def write(self, cypher, params=None):
        self.writes.append((cypher, params))

    def run(self, cypher, params):
        loc = params["location"]
        default_key = eg.LOCATION_DEFAULTS[loc]
        best = None
        for e in params["events"]:
            beh, pri = eg.EVENT_OVERRIDES.get(e, (None, -1))
            if beh and (best is None or pri > best[2]):
                best = (e, beh, pri)
        if best and best[2] > 0:
            return [{"behavior": eg.BEHAVIORS[best[1]],
                     "suppressed": eg.BEHAVIORS[default_key],
                     "source": best[0], "priority": best[2]}]
        return [{"behavior": eg.BEHAVIORS[default_key], "suppressed": None,
                 "source": "location default", "priority": 0}]

    def close(self):
        pass


def test_resolve_event_overrides_location_default(monkeypatch):
    import app.graph.neo4j_client as nc
    monkeypatch.setattr(nc, "Neo4jClient", FakeGraph)
    monkeypatch.setattr(eg, "_seeded", True)
    r = eg.resolve_environment(
        "INT. CONCERT HALL - NIGHT",
        "he suddenly collapses, clutching his chest in pain")
    assert r["source"] == "performer_collapse" and r["priority"] == 10
    assert "frozen in shock" in r["behavior"]
    assert "applauding" in r["suppressed"]


def test_resolve_no_event_keeps_the_default(monkeypatch):
    import app.graph.neo4j_client as nc
    monkeypatch.setattr(nc, "Neo4jClient", FakeGraph)
    monkeypatch.setattr(eg, "_seeded", True)
    r = eg.resolve_environment("INT. CONCERT HALL - NIGHT", "the band plays on")
    assert r["source"] == "location default" and r["suppressed"] is None
    assert "applauding" in r["behavior"]


def test_resolve_unknown_location_is_none():
    assert eg.resolve_environment("INT. SPACESHIP - NIGHT", "he collapses") is None


def test_event_location_gate():
    # a hospital emergency does not apply on a rooftop
    events = [e for e in detect_events("she flatlines, cardiac arrest")
              if (eg.EVENT_LOCATIONS.get(e) is None or "rooftop" in eg.EVENT_LOCATIONS[e])]
    assert "medical_emergency" not in events
