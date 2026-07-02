from app.services.reference_stack import build_reference_stack

CHAR = {"Mia": {"variants": [
    {"plate_image_url": "mia_uniform", "scene_numbers": [1], "is_default": True},
    {"plate_image_url": "mia_dress", "scene_numbers": [2], "is_default": False}]}}


def _bible():
    return {"characters": CHAR, "style_plate": "style", "location_by_scene": {1: "loc1", 2: "loc2"}}


def test_identity_anchor_plus_scene_costume():
    stack = build_reference_stack(
        characters_in_frame=["Mia"], scene_number=2, bible=_bible(),
        prev_last_frame_url="prev", model_cap=9)
    urls = [m["url"] for m in stack]
    # identity (default uniform) locks the face FIRST, then the scene-2 dress outfit,
    # then continuity frame, location, style
    assert urls == ["mia_uniform", "mia_dress", "prev", "loc2", "style"]
    assert urls.index("mia_uniform") < urls.index("mia_dress")


def test_default_scene_dedupes_identity():
    # in the default-outfit scene the identity plate IS the scene plate — no duplicate
    stack = build_reference_stack(
        characters_in_frame=["Mia"], scene_number=1, bible=_bible(),
        prev_last_frame_url=None, model_cap=9)
    urls = [m["url"] for m in stack]
    assert urls.count("mia_uniform") == 1
    assert urls == ["mia_uniform", "loc1", "style"]


def test_cap_trims_from_bottom_keeps_continuity():
    stack = build_reference_stack(
        characters_in_frame=["Mia"], scene_number=1, bible=_bible(),
        prev_last_frame_url="prev", model_cap=2)
    urls = [m["url"] for m in stack]
    # a tight cap keeps character identity + continuity frame; location + style dropped
    assert urls == ["mia_uniform", "prev"]


def test_no_chain_entry_when_prev_none():
    stack = build_reference_stack(
        characters_in_frame=["Mia"], scene_number=1, bible=_bible(),
        prev_last_frame_url=None, model_cap=9)
    assert all(m["url"] != "prev" for m in stack)
