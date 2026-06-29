"""Production cost report. Includes both video cost and Qwen-Max LLM token
cost so the report proves the full run stays within the $40 voucher (Fix #7).
The llm_* fields are populated once token tracking lands (Phase 5); they
default to 0 and the structure is already in place.
"""

WAN_COST_PER_SEC = 0.07
HH_COST_PER_SEC = 0.05


def build_report(
    project_id: str,
    clips: list,
    duration_by_clip: dict,
    total_retries: int,
    wall_clock_minutes: float,
    llm_input_tokens: int = 0,
    llm_output_tokens: int = 0,
    llm_cost_usd: float = 0.0,
    budget: float = 40.0,
) -> dict:
    wan_clips = [c for c in clips if c.model_used == "wan"]
    hh_clips = [c for c in clips if c.model_used != "wan"]
    wan_seconds = sum(duration_by_clip.get(str(c.id), 0) for c in wan_clips)
    hh_seconds = sum(duration_by_clip.get(str(c.id), 0) for c in hh_clips)
    total_seconds = wan_seconds + hh_seconds

    video_cost = wan_seconds * WAN_COST_PER_SEC + hh_seconds * HH_COST_PER_SEC
    grand_total = video_cost + llm_cost_usd

    passed = sum(1 for c in clips if (c.consistency_score or 0) >= 0.6)
    pass_rate = round(passed / len(clips), 2) if clips else 1.0

    return {
        "project_id": project_id,
        "total_duration_seconds": total_seconds,
        "total_clips": len(clips),
        "qwen_max_input_tokens": llm_input_tokens,
        "qwen_max_output_tokens": llm_output_tokens,
        "wan_clips": len(wan_clips),
        "wan_seconds": wan_seconds,
        "happyhorse_clips": len(hh_clips),
        "happyhorse_seconds": hh_seconds,
        "llm_cost_usd": round(llm_cost_usd, 4),
        "video_cost_usd": round(video_cost, 2),
        "grand_total_cost": round(grand_total, 2),
        "budget_usd": budget,
        "within_budget": grand_total <= budget,
        "consistency_pass_rate": pass_rate,
        "total_retries": total_retries,
        "wall_clock_minutes": round(wall_clock_minutes, 1),
    }
