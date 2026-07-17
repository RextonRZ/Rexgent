"""A Wan scenery shot references only location + style (no cast), but the image
legend always told the model to "match each person to their OWN image, never
swap faces or outfits between people" — which invited it to invent people into
an empty landscape. That guide must appear ONLY when a real person plate is in
the reference stack."""
from app.services.reference_stack import image_ref_legend


def test_scenery_only_legend_says_no_people():
    prov = [{"url": "a", "role": "location"}, {"url": "b", "role": "style"}]
    out = image_ref_legend(prov)
    assert "swap faces or outfits between people" not in out
    assert "no people" in out.lower()
    assert "[Image 1]" in out and "[Image 2]" in out


def test_legend_with_a_face_keeps_the_person_guide():
    prov = [{"url": "a", "role": "identity", "character": "Anna"},
            {"url": "b", "role": "location"}]
    out = image_ref_legend(prov)
    assert "match each person to their OWN image" in out
    assert "Anna's face" in out


def test_empty_provenance_is_blank():
    assert image_ref_legend([]) == ""
    assert image_ref_legend(None) == ""


def test_character_plate_label_pins_hair_and_eyewear():
    # "face AND the exact outfit" left hairstyle/accessories/eyewear unpinned:
    # Angeline's hair rendered short in scene 2 while her plate wears it long
    prov = [{"url": "a", "role": "character", "character": "Angeline"}]
    out = image_ref_legend(prov)
    assert "hairstyle" in out
    assert "eyewear" in out or "glasses" in out
    assert "accessor" in out
    assert "outfit" in out


def test_legend_states_exact_headcount_for_two():
    # scene 1 shot 2 rendered TWO copies of Lucas despite the prev-frame
    # no-extra-copies clause — the legend now states the exact headcount
    prov = [{"url": "a", "role": "character", "character": "Angeline"},
            {"url": "b", "role": "character", "character": "Lucas"},
            {"url": "p", "role": "prev_frame"}]
    out = image_ref_legend(prov)
    assert "exactly 2 people" in out
    assert "same person twice" in out


def test_legend_states_exact_headcount_for_one():
    prov = [{"url": "a", "role": "character", "character": "Mia"},
            {"url": "b", "role": "location"}]
    out = image_ref_legend(prov)
    assert "exactly 1 person" in out


def test_costume_only_back_counts_toward_headcount():
    # an OTS back (costume plate only) is still a person in frame
    prov = [{"url": "a", "role": "character", "character": "Angeline"},
            {"url": "b", "role": "costume", "character": "Lucas"}]
    out = image_ref_legend(prov)
    assert "exactly 2 people" in out


def test_scenery_legend_has_no_headcount():
    prov = [{"url": "a", "role": "location"}, {"url": "b", "role": "style"}]
    out = image_ref_legend(prov)
    assert "exactly" not in out
