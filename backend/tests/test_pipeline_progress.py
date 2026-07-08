from app.services.pipeline_progress import STAGE_ORDER, STAGE_PAGES, next_stage


def test_next_stage_is_first_incomplete_in_order():
    progress = {"script": True, "characters": True, "storyboard": False,
                "generate": False, "export": False}
    assert next_stage(progress) == "storyboard"


def test_completed_middle_stage_does_not_hide_earlier_gap():
    # characters missing but storyboard somehow present: the earliest gap wins
    progress = {"script": True, "characters": False, "storyboard": True,
                "generate": False, "export": False}
    assert next_stage(progress) == "characters"


def test_all_done_returns_none():
    assert next_stage({s: True for s in STAGE_ORDER}) is None


def test_every_stage_has_a_page_label():
    assert set(STAGE_PAGES) == set(STAGE_ORDER)
