"""Model tiering: the right Qwen model for each task class.

The hackathon's core constraint is a limited token budget, so the router
keeps qwen-max for the genuinely creative stages (script writing, shot
direction) and hands deterministic JSON work to qwen-flash, with qwen-plus
for judgment calls in between. Every call records which model actually ran
(see usage_tracker.record_usage), so the cost ledger can prove how much of
the pipeline ran on cheap tokens.

An explicit model choice (e.g. the UI's model picker) always wins over the
task route.
"""

CREATIVE = "qwen-max"
ANALYSIS = "qwen-plus"
STRUCTURED = "qwen-flash"

TASK_MODELS: dict[str, str] = {
    # creative writing — the large model earns its cost here
    "script": CREATIVE,
    "storyboard": CREATIVE,
    # judgment / analysis — mid tier
    "judge": ANALYSIS,
    "chat": ANALYSIS,
    "plot_gap": ANALYSIS,
    "ending": ANALYSIS,
    "prompt_craft": ANALYSIS,
    "regen_rewrite": ANALYSIS,
    "appearance": ANALYSIS,
    # deterministic structuring / extraction / formatting — cheap tier
    "structure": STRUCTURED,
    "characters": STRUCTURED,
    "wardrobe": STRUCTURED,
    "set_dress": STRUCTURED,
    "relationships": STRUCTURED,
    "mbti": STRUCTURED,
    "clarify": STRUCTURED,
    "style": STRUCTURED,
    "title": STRUCTURED,
}

# USD per 1k tokens (DashScope international list prices, rounded up so the
# ledger never understates spend). Unknown models fall back to qwen-max rates.
MODEL_RATES: dict[str, dict[str, float]] = {
    "qwen-max": {"in": 0.0016, "out": 0.0064},
    "qwen3-max": {"in": 0.0016, "out": 0.0064},
    "qwen-plus": {"in": 0.0004, "out": 0.0012},
    "qwen-flash": {"in": 0.00005, "out": 0.0004},
    "qwen-vl-max": {"in": 0.0016, "out": 0.0064},
    "qwen3-vl-plus": {"in": 0.0004, "out": 0.0012},
}


def resolve_model(task: str | None, explicit: str | None = None) -> str:
    """Explicit choice wins; otherwise route by task; default to the large model."""
    if explicit:
        return explicit
    return TASK_MODELS.get(task or "", CREATIVE)


def llm_cost_for(model: str | None, in_tokens: int, out_tokens: int) -> float:
    rates = MODEL_RATES.get(model or "") or MODEL_RATES["qwen-max"]
    return round((in_tokens / 1000) * rates["in"]
                 + (out_tokens / 1000) * rates["out"], 6)


def tier_label(model: str | None) -> str:
    """Coarse tier for UI chips: flash | plus | max."""
    m = (model or "").lower()
    if "flash" in m or "turbo" in m:
        return "flash"
    if "plus" in m:
        return "plus"
    return "max"
