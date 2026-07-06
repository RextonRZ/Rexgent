from app.services.reference_stack import (
    build_reference_stack, build_reference_stack_labeled,
)

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


def test_wide_shot_keeps_location_plate():
    stack = build_reference_stack(
        characters_in_frame=["Mia"], scene_number=1, bible=_bible(),
        prev_last_frame_url="prev", model_cap=9, shot_type="LS")
    urls = [m["url"] for m in stack]
    assert "loc1" in urls


def test_tight_shot_drops_location_plate():
    # a close-up must not anchor the whole wide room — it reads as a flat backdrop
    stack = build_reference_stack(
        characters_in_frame=["Mia"], scene_number=1, bible=_bible(),
        prev_last_frame_url="prev", model_cap=9, shot_type="MCU")
    urls = [m["url"] for m in stack]
    assert "loc1" not in urls
    # identity, outfit-continuity and the last-frame chain still anchor it
    assert urls == ["mia_uniform", "prev", "style"]


def test_unknown_shot_type_keeps_location_for_backcompat():
    stack = build_reference_stack(
        characters_in_frame=["Mia"], scene_number=1, bible=_bible(),
        prev_last_frame_url=None, model_cap=9)
    assert "loc1" in [m["url"] for m in stack]


def test_labeled_provenance_matches_media_and_carries_roles():
    media, prov = build_reference_stack_labeled(
        characters_in_frame=["Mia"], scene_number=2, bible=_bible(),
        prev_last_frame_url="prev", model_cap=9)
    assert [m["url"] for m in media] == [p["url"] for p in prov]
    by_url = {p["url"]: p for p in prov}
    assert by_url["mia_uniform"]["role"] == "identity"
    assert by_url["mia_uniform"]["character"] == "Mia"
    assert by_url["mia_dress"]["role"] == "costume"
    assert by_url["prev"]["role"] == "prev_frame"
    assert by_url["loc2"]["role"] == "location"
    assert by_url["style"]["role"] == "style"


def test_labeled_dedupe_keeps_first_role():
    # in the default-outfit scene the identity plate IS the costume plate;
    # provenance keeps the identity role (the reason it is in the stack first)
    _, prov = build_reference_stack_labeled(
        characters_in_frame=["Mia"], scene_number=1, bible=_bible(),
        prev_last_frame_url=None, model_cap=9)
    uniform = [p for p in prov if p["url"] == "mia_uniform"]
    assert len(uniform) == 1
    assert uniform[0]["role"] == "identity"


def test_labeled_cap_trims_provenance_too():
    media, prov = build_reference_stack_labeled(
        characters_in_frame=["Mia"], scene_number=1, bible=_bible(),
        prev_last_frame_url="prev", model_cap=2)
    assert len(media) == len(prov) == 2


def test_scene_anchor_rides_after_prev_frame():
    media, prov = build_reference_stack_labeled(
        characters_in_frame=["Mia"], scene_number=1, bible=_bible(),
        prev_last_frame_url="prev", model_cap=9, shot_type="CU",
        scene_anchor_url="anchor")
    urls = [m["url"] for m in media]
    # a close-up keeps the room via the anchor even though location is dropped
    assert urls == ["mia_uniform", "prev", "anchor", "style"]
    assert next(p for p in prov if p["url"] == "anchor")["role"] == "scene_anchor"


def test_scene_anchor_dedupes_against_prev_frame():
    # second shot of the scene: the anchor IS the previous frame — no duplicate
    media, _ = build_reference_stack_labeled(
        characters_in_frame=["Mia"], scene_number=1, bible=_bible(),
        prev_last_frame_url="frame1", model_cap=9, scene_anchor_url="frame1")
    assert [m["url"] for m in media].count("frame1") == 1


def test_state_change_suppresses_location_plate():
    # once the vase is broken the pristine location plate would contradict
    # the story — it must not anchor the remaining wide shots
    media, _ = build_reference_stack_labeled(
        characters_in_frame=["Mia"], scene_number=1, bible=_bible(),
        prev_last_frame_url="prev", model_cap=9, shot_type="LS",
        suppress_location=True)
    assert "loc1" not in [m["url"] for m in media]
