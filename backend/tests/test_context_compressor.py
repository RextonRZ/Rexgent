import json
from app.services.context_compressor import script_digest


def make_structured(n_scenes=4, lines_per_scene=12):
    return {
        "logline": "A detective discovers her partner is an AI.",
        "characters_mentioned": ["YUKI", "ARIA"],
        "scenes": [
            {
                "scene_number": i + 1,
                "heading": f"INT. OFFICE - NIGHT {i}",
                "location": "office",
                "time_of_day": "night",
                "characters_present": ["YUKI", "ARIA"],
                "emotional_beat": "tension",
                "summary": "They argue about the case.",
                "dialogue_lines": [
                    {"character": "YUKI", "line": "This is a fairly long dialogue line " * 3}
                    for _ in range(lines_per_scene)
                ],
                "stage_directions": ["Yuki paces.", "Aria watches."] * 4,
            }
            for i in range(n_scenes)
        ],
    }


def test_digest_keeps_scene_facts():
    d = script_digest(make_structured())
    assert d["logline"].startswith("A detective")
    assert len(d["scenes"]) == 4
    sc = d["scenes"][0]
    assert sc["scene_number"] == 1
    assert sc["location"] == "office"
    assert sc["characters_present"] == ["YUKI", "ARIA"]
    assert sc["emotional_beat"] == "tension"


def test_digest_drops_dialogue_and_directions():
    d = script_digest(make_structured())
    blob = json.dumps(d)
    assert "dialogue" not in blob
    assert "stage_directions" not in blob


def test_digest_is_much_smaller():
    full = make_structured()
    ratio = len(json.dumps(script_digest(full))) / len(json.dumps(full))
    assert ratio < 0.35


def test_digest_handles_empty():
    assert script_digest(None) == {"logline": None, "characters_mentioned": [], "scenes": []}
    assert script_digest({})["scenes"] == []
