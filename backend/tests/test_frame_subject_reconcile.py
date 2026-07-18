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


def test_name_in_text_matches_a_chinese_name():
    # \b never fires between CJK characters (抱着 and 雪球 are all \w with no
    # boundary between them), so a Chinese-named pet was never seen in the action
    assert _name_in_text("雪球", "安吉琳紧紧抱着雪球，眼里含着泪水") is True
    assert _name_in_text("雪球", "她独自跪在空荡荡的房间里") is False


def test_keeps_chinese_pet_named_in_action_without_a_subject():
    # 雪球 (Snowball) is in-frame with no blocking subject, but the action names
    # it — it must be kept, not dropped as a spurious inclusion
    in_frame = ["安吉琳", "雪球"]
    subjects = [_subj("安吉琳")]
    out = reconcile_frame_with_subjects(in_frame, subjects, "安吉琳抱着雪球坐在床边。")
    assert out == ["安吉琳", "雪球"]


def test_cast_named_in_prose_adds_the_missing_chinese_pet():
    # the structurer dropped the pet 雪球 from characters_present (and listed
    # 玛丽); the scene prose names 雪球, so it is re-added as a character
    from app.services.stage_map import cast_named_in_prose
    scene_chars = [{"name": "安吉琳"}, {"name": "玛丽"}]
    all_cast = [{"name": "安吉琳"}, {"name": "玛丽"}, {"name": "雪球"}]
    prose = "安吉琳透过栅栏看到雪球被拴在树旁，她的眼睛瞪大了。"
    out = cast_named_in_prose(scene_chars, all_cast, prose)
    assert [c["name"] for c in out] == ["安吉琳", "玛丽", "雪球"]


def test_cast_named_in_prose_ignores_the_unmentioned():
    # a cast member NOT named in the prose is not force-added; no duplicates
    from app.services.stage_map import cast_named_in_prose
    scene_chars = [{"name": "安吉琳"}]
    all_cast = [{"name": "安吉琳"}, {"name": "雪球"}, {"name": "路人甲"}]
    prose = "安吉琳独自站在空荡荡的院子里，四下无人。"
    out = cast_named_in_prose(scene_chars, all_cast, prose)
    assert [c["name"] for c in out] == ["安吉琳"]
