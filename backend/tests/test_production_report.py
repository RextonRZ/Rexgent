from types import SimpleNamespace
from app.services.production_report import build_report


def _clip(cid, model, score):
    return SimpleNamespace(id=cid, model_used=model, consistency_score=score)


def test_report_sums_costs_and_within_budget():
    clips = [_clip("a", "wan", 0.9), _clip("b", "happyhorse", 0.8)]
    durations = {"a": 5, "b": 4}
    report = build_report(
        project_id="p1", clips=clips, duration_by_clip=durations,
        total_retries=1, wall_clock_minutes=12.5,
        llm_input_tokens=10000, llm_output_tokens=4000, llm_cost_usd=0.041,
    )
    # wan 5s*0.07 + hh 4s*0.05 = 0.35 + 0.20 = 0.55 video, + 0.041 llm
    assert report["video_cost_usd"] == 0.55
    assert report["grand_total_cost"] == 0.59
    assert report["within_budget"] is True
    assert report["total_clips"] == 2


def test_report_flags_over_budget():
    # 600s of Wan = $42 video -> over $40
    clips = [_clip("a", "wan", 0.9)]
    durations = {"a": 600}
    report = build_report(
        project_id="p1", clips=clips, duration_by_clip=durations,
        total_retries=0, wall_clock_minutes=30,
    )
    assert report["within_budget"] is False


def test_pass_rate():
    clips = [_clip("a", "wan", 0.9), _clip("b", "wan", 0.3)]
    report = build_report(
        project_id="p1", clips=clips, duration_by_clip={"a": 5, "b": 5},
        total_retries=0, wall_clock_minutes=1,
    )
    assert report["consistency_pass_rate"] == 0.5
