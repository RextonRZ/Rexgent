from app.director.director import apply_guardrails
from app.director.types import PlannedShot


def _shot(size="MS", purpose="dialogue", covers=(), lens="50mm"):
    return PlannedShot(purpose=purpose, shot_size=size, camera_movement="STATIC",
                       lens=lens, composition="rule_of_thirds", intended_duration=5.0,
                       covers_lines=list(covers), action_beat="a beat")


def test_coverage_reinserts_a_dropped_line():
    # 3 lines exist; the plan only covers 0 and 2 -> line 1 must be folded back in
    plan = [_shot(covers=[0]), _shot(covers=[2])]
    out = apply_guardrails(plan, n_lines=3, budget=5)
    covered = sorted(i for s in out.shots for i in s.covers_lines)
    assert covered == [0, 1, 2]


def test_no_two_consecutive_same_size():
    plan = [_shot(size="MS", covers=[0]), _shot(size="MS", covers=[1])]
    out = apply_guardrails(plan, n_lines=2, budget=5)
    sizes = [s.shot_size for s in out.shots]
    assert sizes[0] != sizes[1]


def test_budget_never_exceeded():
    plan = [_shot(purpose="reaction", covers=[]) for _ in range(9)] + [_shot(covers=[0])]
    out = apply_guardrails(plan, n_lines=1, budget=4)
    assert len(out.shots) <= 4
    # the dialogue line survives the trim (non-dialogue beats are dropped first)
    assert any(0 in s.covers_lines for s in out.shots)


def test_incompatible_size_lens_snapped():
    plan = [_shot(size="EWS", purpose="establishing", lens="85mm", covers=[])]
    out = apply_guardrails(plan, n_lines=0, budget=5)
    assert not (out.shots[0].shot_size == "EWS" and out.shots[0].lens == "85mm")
