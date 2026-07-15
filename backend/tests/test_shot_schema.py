"""Regression: the Director/cinematic Stager writes rich descriptive lighting,
colour_mood and emotional_beat (full sentences) onto shots. Those columns were
VARCHAR(50)/VARCHAR(255) and overflowed, throwing StringDataRightTruncation on
the scene's batch insert — 0 shots saved, the board crashed, and the storyboard
UI hung forever. They must be unbounded, and the bounded enum-ish columns must
never let one over-long LLM value fail the whole batch insert."""
from app.models.shot import Shot, clamp_bounded_strings


def test_descriptive_columns_are_unbounded():
    # lighting/colour_mood/emotional_beat now hold LLM-authored descriptions
    for name in ("lighting", "colour_mood", "emotional_beat"):
        col = Shot.__table__.c[name]
        assert getattr(col.type, "length", None) is None, (
            f"shots.{name} must be unbounded Text to hold Director descriptions"
        )


def test_clamp_truncates_bounded_string_fields():
    long_move = "a very slow deliberate dolly-in pushing past her shoulder " * 3
    out = clamp_bounded_strings({
        "camera_movement": long_move,
        "shot_type": "MEDIUM-CLOSE-OVER-THE-SHOULDER-EXTRA-LONG",
        "lighting": "x" * 500,  # unbounded column: must pass through untouched
    })
    assert len(out["camera_movement"]) <= Shot.__table__.c["camera_movement"].type.length
    assert len(out["shot_type"]) <= Shot.__table__.c["shot_type"].type.length
    assert out["lighting"] == "x" * 500


def test_clamp_leaves_normal_values_untouched():
    v = {"camera_movement": "PAN_LEFT", "shot_type": "MS", "dialogue": None,
         "colour_mood": "Cool, muted grays and blues to heighten the suspense"}
    assert clamp_bounded_strings(dict(v)) == v
