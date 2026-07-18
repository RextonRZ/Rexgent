"""An action that names a character NOT in the shot's frame ("glancing back at
Anna" in a Deok-hyun-only shot) made the video model hallucinate the absent
character, worst on Wan. Off-frame cast names must be stripped from the action
before it reaches the prompt; in-frame names are kept for the compiler."""
from app.services.guardrails import mask_offscreen_names

_CAST = ["Deok-hyun", "Anna", "Middle-Aged Man", "Middle-Aged Woman"]


def test_offscreen_name_is_stripped_but_in_frame_kept():
    action = "Deok-hyun's face shows visible shock and discomfort, glancing back at Anna."
    out = mask_offscreen_names(action, ["Deok-hyun"], _CAST)
    assert "Anna" not in out       # off-frame -> removed, so Wan can't render her
    assert "Deok-hyun" in out      # in-frame -> kept (compiler resolves it later)


def test_all_names_kept_when_everyone_is_in_frame():
    out = mask_offscreen_names("Anna and Deok-hyun embrace", ["Anna", "Deok-hyun"], _CAST)
    assert "Anna" in out and "Deok-hyun" in out


def test_empty_and_none_action_are_safe():
    assert mask_offscreen_names("", ["Deok-hyun"], _CAST) == ""
    assert mask_offscreen_names(None, ["Deok-hyun"], _CAST) == ""


_CAST_ZH = ["安吉琳", "玛丽", "雪球"]


def test_offscreen_chinese_name_is_stripped():
    # \b never fires between CJK characters, so an off-frame zh name survived
    # into the prompt and Wan rendered it literally (雪球 = a white fluffy ball
    # painted beside the cast)
    action = "安吉琳透过栅栏看到雪球，显得很惊讶。"
    out = mask_offscreen_names(action, ["安吉琳"], _CAST_ZH)
    assert "雪球" not in out
    assert "安吉琳" in out          # in-frame -> kept


def test_chinese_possessive_is_eaten_with_the_name():
    # 雪球的项圈 -> 项圈, not an orphaned 的项圈 (mirrors "Bear's" -> "")
    from app.services.guardrails import strip_character_names
    out = strip_character_names("镜头扫过雪球的项圈", ["雪球"])
    assert "雪球" not in out
    assert "的项圈" not in out
    assert "项圈" in out
