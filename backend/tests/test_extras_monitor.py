"""script_generate's rule ("an unnamed presence may appear once; a recurring
figure must be NAMED into the cast") was a hope in the prompt with no
downstream enforcement — the LLM could ship a figure that renders as a
different person every shot, silently. detect_recurring_extras flags it:
a WARNING that gets surfaced, never a block."""
from app.services.extras_monitor import detect_recurring_extras

CAST = ["Anna", "Deok-hyun"]


def _shot(scene, shot, action="", notes="", in_frame=()):
    return {"scene_number": scene, "shot_number": shot, "action": action,
            "notes": notes, "characters_in_frame": list(in_frame)}


def test_clean_board_yields_no_findings():
    shots = [
        _shot(1, 1, "Waves crash against the cliff."),
        _shot(1, 2, "Anna turns to face the ocean.", in_frame=["Anna"]),
    ]
    assert detect_recurring_extras(shots, CAST) == []


def test_one_time_unnamed_presence_is_allowed():
    # the script rule: a shadowy figure may appear ONCE (e.g. a cliffhanger)
    shots = [
        _shot(1, 1, "A shadowy figure watches from the treeline."),
        _shot(1, 2, "Anna walks on, unaware.", in_frame=["Anna"]),
    ]
    assert detect_recurring_extras(shots, CAST) == []


def test_recurring_figure_across_shots_is_flagged():
    shots = [
        _shot(1, 2, "A shadowy figure watches from the treeline."),
        _shot(1, 5, "The shadowy figure steps closer."),
    ]
    out = detect_recurring_extras(shots, CAST)
    assert len(out) == 1
    assert out[0]["figure"] == "shadowy figure"
    assert out[0]["shots"] == [(1, 2), (1, 5)]
    assert "different person" in out[0]["warning"]


def test_recurring_figure_across_scenes_names_the_scenes():
    shots = [
        _shot(1, 3, "A hooded man waits by the gate."),
        _shot(2, 1, notes="the hooded man from before is here again"),
    ]
    out = detect_recurring_extras(shots, CAST)
    assert len(out) == 1
    assert out[0]["scenes"] == [1, 2]


def test_bare_indefinite_mentions_are_not_the_same_person():
    # "a man" in two shots is two passersby, not one recurring presence
    shots = [
        _shot(1, 1, "A man walks past the cafe."),
        _shot(2, 4, "A man sweeps the street."),
    ]
    assert detect_recurring_extras(shots, CAST) == []


def test_definite_article_counts_as_established_referent():
    shots = [
        _shot(1, 1, "The stranger lingers at the door."),
        _shot(1, 3, "The stranger is gone."),
    ]
    out = detect_recurring_extras(shots, CAST)
    assert len(out) == 1 and out[0]["figure"] == "stranger"


def test_non_cast_name_in_frame_is_flagged_even_once():
    # defense in depth: board-time filtering should prevent this, but a leaked
    # non-cast identity must still surface — it has no plate to lock
    shots = [_shot(2, 1, in_frame=["Anna", "VILLAGER"])]
    out = detect_recurring_extras(shots, CAST)
    assert len(out) == 1
    assert out[0]["figure"] == "VILLAGER"
    assert "not in the cast" in out[0]["warning"]


def test_cast_name_variants_are_not_extras():
    # qualifiers and bare first names resolve to cast, never flagged
    shots = [_shot(1, 1, in_frame=["DEOK-HYUN (O.S.)", "ANNA"])]
    assert detect_recurring_extras(shots, CAST) == []
