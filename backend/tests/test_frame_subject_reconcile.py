"""A character listed in characters_in_frame but never given a blocking subject
AND not named in the action is spurious (the antagonist literally named 'Man'
turning up in a two-person beat). It has no position, yet the render would send
its plate as a floating face reference. reconcile_frame_with_subjects drops it."""
from app.services.stage_map import reconcile_frame_with_subjects, _name_in_text


def _subj(name):
    return {"character": name, "screen_side": "left", "frame_position": "MG"}


def test_drops_unstaged_character_not_in_action():
    # the real S1-3 case: Deok-hyun + Anna are staged; Man is in-frame but has
    # no subject and the action is only about the other two
    in_frame = ["Deok-hyun", "Anna", "Man"]
    subjects = [_subj("Deok-hyun"), _subj("Anna")]
    action = "Deok-hyun approaches Anna with a concerned expression"
    assert reconcile_frame_with_subjects(in_frame, subjects, action) == ["Deok-hyun", "Anna"]


def test_keeps_character_with_a_subject():
    in_frame = ["Anna", "Deok-hyun"]
    subjects = [_subj("Anna"), _subj("Deok-hyun")]
    out = reconcile_frame_with_subjects(in_frame, subjects, "they sit together")
    assert out == ["Anna", "Deok-hyun"]


def test_keeps_unstaged_character_named_in_action():
    # no subject, but the action names them -> intended, keep (a stager omission,
    # not a spurious inclusion)
    in_frame = ["Anna", "Rex"]
    subjects = [_subj("Anna")]
    out = reconcile_frame_with_subjects(in_frame, subjects, "Rex storms through the door")
    assert out == ["Anna", "Rex"]


def test_no_subjects_leaves_frame_intact():
    # a shot with no blocking at all is a different case — do not strip its cast
    in_frame = ["Anna", "Deok-hyun", "Man"]
    out = reconcile_frame_with_subjects(in_frame, [], "a wide establishing view")
    assert out == ["Anna", "Deok-hyun", "Man"]


def test_order_preserved():
    in_frame = ["Zoe", "Anna", "Man", "Rex"]
    subjects = [_subj("Rex"), _subj("Zoe"), _subj("Anna")]
    out = reconcile_frame_with_subjects(in_frame, subjects, "no names here")
    assert out == ["Zoe", "Anna", "Rex"]      # Man dropped, others keep order


def test_common_noun_name_not_matched_by_prose():
    # 'Man' as a name must NOT be kept just because the action says 'a man walks'
    in_frame = ["Anna", "Man"]
    subjects = [_subj("Anna")]
    out = reconcile_frame_with_subjects(in_frame, subjects, "a man walks past in the distance")
    assert out == ["Anna"]


def test_name_in_text_matches_first_token_and_full_name():
    assert _name_in_text("Deok-hyun", "Deok-hyun approaches") is True
    assert _name_in_text("Eirik Halden", "then Eirik turns") is True   # first token
    assert _name_in_text("Man", "a man walks by") is False             # stopword
    assert _name_in_text("Anna", "the room is empty") is False
