"""Pure planner for the verify-and-repair ladder. No I/O — given a continuity
`guard` (face/outfit/background sub-scores + overall) it decides which repair
strategies to try, cheapest first, bounded by how many extra renders remain:

  reseed    - re-render the same way with a fresh seed (a bad roll)
  reanchor  - re-render as an r2v anchor with the full plate stack (the frame drifted)
  videoedit - patch the worst component (outfit/face) onto the existing clip

The runner executes them in order and keeps the best-scoring result.
"""

_COMPONENTS = (("face", "face_score"), ("outfit", "outfit_score"),
               ("background", "background_score"))


def worst_component(guard: dict) -> str | None:
    """The lowest present sub-score's name (face/outfit/background), or None
    when no sub-score is available."""
    present = [(name, guard.get(key)) for name, key in _COMPONENTS
               if guard.get(key) is not None]
    if not present:
        return None
    return min(present, key=lambda kv: kv[1])[0]


def repair_steps(guard: dict, role: str, renders_left: int) -> list[str]:
    """Ordered repair strategies to try for a failed shot, cheapest first,
    truncated to renders_left. Empty when nothing is left to spend."""
    if renders_left <= 0:
        return []
    steps = ["reseed"]
    worst = worst_component(guard)
    if role in ("continue_hold", "continue_reangle") and worst in ("face", "outfit"):
        steps.append("reanchor")
    if worst in ("outfit", "face"):
        steps.append("videoedit")
    return steps[:renders_left]
