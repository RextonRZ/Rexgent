"""A costume change is earned by a passage of days or a motivated change of
clothes, never by a scene cut. When the script earns nothing, every character
wears ONE outfit for the whole episode — a fragmented per-scene plan (near-
identical outfits that read as a continuity error and cost extra plates) is
collapsed to a single outfit."""
from app.services.wardrobe_planner import (
    script_earns_wardrobe_change, collapse_to_single_outfit,
)


def _scene(n, heading="INT. ROOM - DAY", desc="", directions=None):
    return {"number": n, "heading": heading, "description": desc,
            "stage_directions": directions or []}


class TestEarnsChange:
    def test_plain_single_day_earns_nothing(self):
        structured = {"scenes": [_scene(1), _scene(2, desc="They keep talking.")]}
        assert script_earns_wardrobe_change(structured) is False

    def test_time_jump_in_heading_earns_change(self):
        structured = {"scenes": [_scene(1), _scene(2, desc="The next morning, she returns.")]}
        assert script_earns_wardrobe_change(structured) is True

    def test_days_later_earns_change(self):
        structured = {"scenes": [_scene(1, desc="Three days later at the harbour.")]}
        assert script_earns_wardrobe_change(structured) is True

    def test_motivated_change_earns_it(self):
        structured = {"scenes": [_scene(1, directions=["She is soaked from the rain."])]}
        assert script_earns_wardrobe_change(structured) is True

    def test_changes_into_earns_it(self):
        structured = {"scenes": [_scene(1, desc="He changes into a suit for the wedding.")]}
        assert script_earns_wardrobe_change(structured) is True

    def test_empty_script_earns_nothing(self):
        assert script_earns_wardrobe_change({}) is False
        assert script_earns_wardrobe_change({"scenes": []}) is False


class TestCollapse:
    def test_fragmented_plan_collapses_to_one_outfit(self):
        planned = {"Anna": [
            {"label": "look1", "outfit_description": "blue linen shirt", "scene_numbers": [1]},
            {"label": "look2", "outfit_description": "blue cotton shirt", "scene_numbers": [2]},
        ]}
        out = collapse_to_single_outfit(planned)
        assert len(out["Anna"]) == 1
        v = out["Anna"][0]
        assert v["scene_numbers"] == [1, 2]      # union of every scene
        assert v["is_default"] is True
        assert v["outfit_description"] == "blue linen shirt"   # the primary wins

    def test_default_variant_is_the_one_kept(self):
        planned = {"Deok": [
            {"outfit_description": "sweater", "scene_numbers": [2]},
            {"outfit_description": "jacket", "scene_numbers": [1], "is_default": True},
        ]}
        out = collapse_to_single_outfit(planned)
        assert out["Deok"][0]["outfit_description"] == "jacket"
        assert out["Deok"][0]["scene_numbers"] == [1, 2]

    def test_already_single_outfit_is_unchanged_in_shape(self):
        planned = {"Mara": [{"outfit_description": "red coat", "scene_numbers": [1, 2, 3]}]}
        out = collapse_to_single_outfit(planned)
        assert len(out["Mara"]) == 1
        assert out["Mara"][0]["scene_numbers"] == [1, 2, 3]

    def test_empty_variants_pass_through(self):
        assert collapse_to_single_outfit({"X": []}) == {"X": []}
        assert collapse_to_single_outfit({}) == {}
