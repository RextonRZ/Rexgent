"""Qwen-Max token accounting (Fix #7).

A process-global tracker accumulates token usage from every Qwen call so the
budget dashboard and production report can show LLM cost alongside video cost.

Scope note: accounting is per-process (the FastAPI app process tracks
script/analysis/storyboard calls; the Celery worker tracks generation-time
calls). For the single-project hackathon demo this gives an accurate
"LLM tokens used" figure.
"""
from app.config import get_settings


class UsageTracker:
    def __init__(self, input_per_1k: float, output_per_1k: float):
        self.input_per_1k = input_per_1k
        self.output_per_1k = output_per_1k
        self.total_input = 0
        self.total_output = 0

    def add(self, prompt_tokens: int | None, completion_tokens: int | None) -> None:
        self.total_input += int(prompt_tokens or 0)
        self.total_output += int(completion_tokens or 0)

    @property
    def cost_usd(self) -> float:
        return (self.total_input / 1000) * self.input_per_1k + (
            self.total_output / 1000
        ) * self.output_per_1k

    def snapshot(self) -> dict:
        return {
            "input_tokens": self.total_input,
            "output_tokens": self.total_output,
            "cost_usd": round(self.cost_usd, 4),
        }

    def reset(self) -> None:
        self.total_input = 0
        self.total_output = 0


_global: UsageTracker | None = None


def global_usage() -> UsageTracker:
    global _global
    if _global is None:
        s = get_settings()
        _global = UsageTracker(s.qwen_max_input_cost_per_1k, s.qwen_max_output_cost_per_1k)
    return _global


def record_usage(usage) -> None:
    """Record a response.usage object (OpenAI-compatible) into the global tracker."""
    if usage is None:
        return
    try:
        global_usage().add(
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
        )
    except Exception:  # noqa: BLE001
        pass
