from types import SimpleNamespace
from app.services.production_report import build_report


def _clip(cid, model, score):
    return SimpleNamespace(id=cid, model_used=model, consistency_score=score)


def test_report_sums_costs_and_within_budget():
    clips = [_clip("a", "wan", 90), _clip("b", "happyhorse", 80)]
    durations = {"a": 5, "b": 4}
    report = build_report(
        project_id="p1", clips=clips, duration_by_clip=durations,
        total_retries=1, wall_clock_minutes=12.5,
        llm_input_tokens=10000, llm_output_tokens=4000, llm_cost_usd=0.041,
    )
    # wan 5s*0.15 + hh 4s*0.108 = 0.75 + 0.432 = 1.18 video, + 0.041 llm
    assert report["video_cost_usd"] == 1.18
    assert report["grand_total_cost"] == 1.22
    assert report["within_budget"] is True
    assert report["total_clips"] == 2


def test_report_flags_over_budget():
    # 600s of Wan = $90 video -> over $40
    clips = [_clip("a", "wan", 90)]
    durations = {"a": 600}
    report = build_report(
        project_id="p1", clips=clips, duration_by_clip=durations,
        total_retries=0, wall_clock_minutes=30,
    )
    assert report["within_budget"] is False


def test_pass_rate_uses_0_to_100_scale():
    # scores are 0-100 (ContinuityAgent PASS_THRESHOLD = 55): 82 passes, 30 fails
    clips = [_clip("a", "wan", 82), _clip("b", "wan", 30)]
    report = build_report(
        project_id="p1", clips=clips, duration_by_clip={"a": 5, "b": 5},
        total_retries=0, wall_clock_minutes=1,
    )
    assert report["consistency_pass_rate"] == 0.5


def test_pass_rate_not_fooled_by_fraction_scores():
    # regression: a 0.9 on the old 0-1 scale is a FAILING 0.9/100 today
    clips = [_clip("a", "wan", 0.9)]
    report = build_report(
        project_id="p1", clips=clips, duration_by_clip={"a": 5},
        total_retries=0, wall_clock_minutes=1,
    )
    assert report["consistency_pass_rate"] == 0.0
