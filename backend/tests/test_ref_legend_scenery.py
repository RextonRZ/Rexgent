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
