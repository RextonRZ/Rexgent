from app.services.reference_stack import (
    build_reference_stack, build_reference_stack_labeled,
)

CHAR = {"Mia": {"variants": [
    {"plate_image_url": "mia_uniform", "scene_numbers": [1], "is_default": True},
    {"plate_image_url": "mia_dress", "scene_numbers": [2], "is_default": False}]}}


def _bible():
    return {"characters": CHAR, "style_plate": "style", "location_by_scene": {1: "loc1", 2: "loc2"}}


def test_one_plate_carries_face_and_scene_outfit():
    stack = build_reference_stack(
        characters_in_frame=["Mia"], scene_number=2, bible=_bible(),
        prev_last_frame_url="prev", model_cap=9)
    urls = [m["url"] for m in stack]
    # ONE plate per character: the scene-2 dress plate (face + outfit), then
    # location and style. The default uniform is NOT also sent — two plates of
    # the same person in different outfits drifted the face. Frames never ride.
    assert urls == ["mia_dress", "loc2", "style"]
    assert "mia_uniform" not in urls


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
    # a tight cap keeps character identity + the location; style dropped
    assert urls == ["mia_uniform", "loc1"]


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
    # a true close-up must not anchor the whole wide room — it reads as a
    # flat backdrop behind a face that fills the frame
    stack = build_reference_stack(
        characters_in_frame=["Mia"], scene_number=1, bible=_bible(),
        prev_last_frame_url="prev", model_cap=9, shot_type="CU")
    urls = [m["url"] for m in stack]
    assert "loc1" not in urls
    # identity and style anchor it; prev_frame never rides as a reference
    assert urls == ["mia_uniform", "style"]


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
    assert by_url["mia_dress"]["role"] == "character"   # one plate: face + outfit
    assert by_url["mia_dress"]["character"] == "Mia"
    assert "mia_uniform" not in by_url                  # no separate identity plate
    assert "prev" not in by_url                         # frames never ride as refs
    assert by_url["loc2"]["role"] == "location"
    assert by_url["style"]["role"] == "style"


def test_labeled_single_plate_is_the_character():
    # one plate per character, carrying face + outfit, tagged "character"
    _, prov = build_reference_stack_labeled(
        characters_in_frame=["Mia"], scene_number=1, bible=_bible(),
        prev_last_frame_url=None, model_cap=9)
    uniform = [p for p in prov if p["url"] == "mia_uniform"]
    assert len(uniform) == 1
    assert uniform[0]["role"] == "character"


def test_labeled_cap_trims_provenance_too():
    media, prov = build_reference_stack_labeled(
        characters_in_frame=["Mia"], scene_number=1, bible=_bible(),
        prev_last_frame_url="prev", model_cap=2)
    assert len(media) == len(prov) == 2


def test_prev_frame_never_rides_but_the_faceless_anchor_does():
    # prev_frame CONTAINS the cast in-picture: attached beside the identity
    # plates it renders as an EXTRA COPY of the characters (two Deok-hyuns).
    # scene_anchor DOES ride — the runner only assigns it from a PEOPLE-FREE
    # shot's frame (the scenery clip), so it anchors the room and connects
    # the peopled shots to the Wan scenery without anyone to duplicate.
    media, prov = build_reference_stack_labeled(
        characters_in_frame=["Mia"], scene_number=1, bible=_bible(),
        prev_last_frame_url="prev", model_cap=9, shot_type="CU",
        scene_anchor_url="anchor")
    urls = [m["url"] for m in media]
    assert "prev" not in urls
    assert "anchor" in urls
    assert next(p for p in prov if p["url"] == "anchor")["role"] == "scene_anchor"
    assert all(p["role"] != "prev_frame" for p in prov)


def test_mcu_keeps_the_location_plate():
    # an MCU scene-opener invented a whole different cabin (bg 0.30) because
    # tight framings dropped the plate; only CU/ECU are exempt now
    stack = build_reference_stack(
        characters_in_frame=["Mia"], scene_number=1, bible=_bible(),
        prev_last_frame_url=None, model_cap=9, shot_type="MCU")
    assert "loc1" in [m["url"] for m in stack]


def test_state_change_suppresses_location_plate():
    # once the vase is broken the pristine location plate would contradict
    # the story — it must not anchor the remaining wide shots
    media, _ = build_reference_stack_labeled(
        characters_in_frame=["Mia"], scene_number=1, bible=_bible(),
        prev_last_frame_url="prev", model_cap=9, shot_type="LS",
        suppress_location=True)
    assert "loc1" not in [m["url"] for m in media]


# two characters: Rex (subject) and Mia (foreground shoulder in a reveal)
TWO = {
    "Rex": {"variants": [{"plate_image_url": "rex_face", "scene_numbers": [1], "is_default": True}]},
    "Mia": {"variants": [{"plate_image_url": "mia_face", "scene_numbers": [1], "is_default": True}]},
}


def _two_bible():
    return {"characters": TWO, "style_plate": "style", "location_by_scene": {1: "loc1"}}


def test_foreground_character_gets_outfit_only():
    # Mia is only a foreground shoulder: her plate is the OUTFIT reference (face
    # unseen), never a face subject, so the model doesn't render her front-and-
    # centre in Rex's reveal.
    _, prov = build_reference_stack_labeled(
        characters_in_frame=["Rex", "Mia"], scene_number=1, bible=_two_bible(),
        prev_last_frame_url=None, model_cap=9, shot_type="OTS",
        foreground_characters=["Mia"])
    roles = {(p["url"], p["role"]) for p in prov}
    assert ("rex_face", "character") in roles   # subject: one plate, face + outfit
    assert ("mia_face", "costume") in roles      # foreground: outfit only
    assert ("mia_face", "character") not in roles
    assert ("mia_face", "identity") not in roles


def test_subject_ordered_before_foreground_under_tight_cap():
    # a tight cap must keep the subject's face, not the foreground occluder's plate
    media, _ = build_reference_stack_labeled(
        characters_in_frame=["Mia", "Rex"], scene_number=1, bible=_two_bible(),
        prev_last_frame_url=None, model_cap=1, shot_type="OTS",
        foreground_characters=["Mia"])
    assert [m["url"] for m in media] == ["rex_face"]


def test_no_foreground_both_get_character_plate():
    # a genuine two-shot: both people get their single face+outfit plate
    _, prov = build_reference_stack_labeled(
        characters_in_frame=["Rex", "Mia"], scene_number=1, bible=_two_bible(),
        prev_last_frame_url=None, model_cap=9)
    chars = {p["url"] for p in prov if p["role"] == "character"}
    assert chars == {"rex_face", "mia_face"}


def test_ots_and_pov_keep_location_plate():
    """An over-the-shoulder frames its subject against REAL visible room —
    rendering it without the location anchor let the model reinvent the set
    (bg 0.30 vs 0.85+ on same-scene MS shots). OTS and POV now anchor the room."""
    for st in ("OTS", "POV"):
        stack = build_reference_stack(
            characters_in_frame=["Mia"], scene_number=1, bible=_bible(),
            prev_last_frame_url="prev", model_cap=9, shot_type=st)
        assert "loc1" in [m["url"] for m in stack], st
