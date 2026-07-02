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
    # character (scene-2 dress) first, then style, then location, then chain
    assert urls == ["mia_dress", "style", "loc2", "prev"]


def test_cap_trims_from_bottom():
    stack = build_reference_stack(
        characters_in_frame=["Mia"], scene_number=1, bible=_bible(),
        prev_last_frame_url="prev", model_cap=2)
    urls = [m["url"] for m in stack]
    assert urls == ["mia_uniform", "style"]  # location + chain dropped


def test_chain_ignored_across_scene_boundary():
    stack = build_reference_stack(
        characters_in_frame=["Mia"], scene_number=1, bible=_bible(),
        prev_last_frame_url=None, model_cap=9)
    assert all(m["url"] != "prev" for m in stack)
