from app.services.reference_stack import build_reference_stack

CHAR = {"Mia": {"variants": [
    {"plate_image_url": "mia_uniform", "scene_numbers": [1], "is_default": True},
    {"plate_image_url": "mia_dress", "scene_numbers": [2], "is_default": False}]}}


def _bible():
    return {"characters": CHAR, "style_plate": "style", "location_by_scene": {1: "loc1", 2: "loc2"}}


def test_priority_order_and_scene_costume():
    stack = build_reference_stack(
        characters_in_frame=["Mia"], scene_number=2, bible=_bible(),
        prev_last_frame_url="prev", model_cap=9)
    urls = [m["url"] for m in stack]
    # character (scene-2 dress) first, then the continuity frame, then location, then style
    assert urls == ["mia_dress", "prev", "loc2", "style"]


def test_cap_trims_from_bottom_keeps_continuity():
    stack = build_reference_stack(
        characters_in_frame=["Mia"], scene_number=1, bible=_bible(),
        prev_last_frame_url="prev", model_cap=2)
    urls = [m["url"] for m in stack]
    # a tight cap keeps character + continuity frame; location + style dropped
    assert urls == ["mia_uniform", "prev"]


def test_no_chain_entry_when_prev_none():
    stack = build_reference_stack(
        characters_in_frame=["Mia"], scene_number=1, bible=_bible(),
        prev_last_frame_url=None, model_cap=9)
    assert all(m["url"] != "prev" for m in stack)
