from app.services.continuity_repair import worst_component, repair_steps


def _g(face=0.9, outfit=0.9, bg=0.9, score=80, passed=True):
    return {"face_score": face, "outfit_score": outfit, "background_score": bg,
            "continuity_score": score, "overall_pass": passed}


def test_worst_component_picks_lowest_present():
    assert worst_component(_g(face=0.4, outfit=0.8, bg=0.9)) == "face"
    assert worst_component(_g(face=0.9, outfit=0.3, bg=0.9)) == "outfit"


def test_worst_component_ignores_none_scores():
    assert worst_component(_g(face=None, outfit=0.3, bg=0.9)) == "outfit"


def test_worst_component_none_when_all_missing():
    assert worst_component(_g(face=None, outfit=None, bg=None)) is None


def test_no_steps_when_no_renders_left():
    assert repair_steps(_g(score=40, passed=False), role="anchor", renders_left=0) == []


def test_reseed_is_always_first():
    steps = repair_steps(_g(score=40, passed=False), role="anchor", renders_left=2)
    assert steps[0] == "reseed"


def test_continue_hold_face_drift_adds_reanchor():
    steps = repair_steps(_g(face=0.3, score=40, passed=False),
                         role="continue_hold", renders_left=3)
    assert "reanchor" in steps


def test_low_outfit_adds_videoedit():
    steps = repair_steps(_g(outfit=0.2, score=40, passed=False),
                         role="anchor", renders_left=3)
    assert "videoedit" in steps


def test_steps_capped_to_renders_left():
    steps = repair_steps(_g(face=0.2, outfit=0.2, score=30, passed=False),
                         role="continue_hold", renders_left=1)
    assert len(steps) == 1
