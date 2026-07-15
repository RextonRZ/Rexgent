"""The Stager LLM sometimes flattens a whole blocking subject into the character
field, in `key=value` form ("ANNA: frame_position=center, screen_side=left, ...").
The un-flattener only handled `key:value`, so the geometry stayed trapped in one
string and the top-down camera plan drew nothing. It must handle both."""
from app.services.stage_map import _parse_flat_subject, normalize_subjects

_EQUALS = ("ANNA: frame_position=center, screen_side=left, facing=right, "
           "eyeline=down, posture=sitting, action=whispering")


def test_parse_equals_format():
    out = _parse_flat_subject(_EQUALS)
    assert out["character"] == "ANNA"
    assert out["frame_position"] == "center"
    assert out["screen_side"] == "left"
    assert out["facing"] == "right"
    assert out["posture"] == "sitting"


def test_parse_colon_format_still_works():
    out = _parse_flat_subject("character_name: IM SOL, frame_position: FG, screen_side: left")
    assert out["character"] == "IM SOL"
    assert out["screen_side"] == "left"


def test_normalize_unflattens_the_camera_geometry():
    out = normalize_subjects([{"character": _EQUALS}])
    assert out is not None and len(out) == 1
    s = out[0]
    # the frontend camera plan reads these keys; they must exist as real fields
    assert s["character"] == "ANNA"
    assert s["screen_side"] == "left" and s["facing"] == "right"
