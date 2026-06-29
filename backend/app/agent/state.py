from typing import TypedDict, Any


class PipelineState(TypedDict, total=False):
    project_id: str
    premise: str
    genre: str
    tone: str
    language: str            # "en" | "zh"
    target_length: int       # minutes per episode
    episode_count: int
    dispatch_video: bool     # when False, plan only — do not spend the voucher
    script_id: str
    structured: dict[str, Any]
    judgement: dict[str, Any]
    revise_count: int
    characters: list[dict]
    shots: list[dict]
    budget: dict[str, Any]
    job_id: str
    report: dict[str, Any]
    auto: bool
