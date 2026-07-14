from app.director import knowledge_base as kb
from app.director.types import PlannedShot, ShotPlan


def _enforce_coverage(shots: list[PlannedShot], n_lines: int) -> None:
    """Every dialogue-line index appears exactly once. Dropped lines are folded
    into the nearest dialogue shot (or a new one). Duplicates are de-duped."""
    seen: set[int] = set()
    for s in shots:
        s.covers_lines = [i for i in s.covers_lines if 0 <= i < n_lines and i not in seen]
        seen.update(s.covers_lines)
    missing = [i for i in range(n_lines) if i not in seen]
    if not missing:
        return
    dialogue_shots = [s for s in shots if kb.SHOT_PURPOSES.get(s.purpose, {}).get("dialogue")]
    for i in missing:
        if dialogue_shots:
            dialogue_shots[0].covers_lines.append(i)
        else:
            shots.append(PlannedShot(purpose="dialogue", shot_size="MS",
                                     camera_movement="STATIC", lens="50mm",
                                     composition="rule_of_thirds", intended_duration=5.0,
                                     covers_lines=[i], action_beat="delivers the line"))


def _enforce_no_repeat(shots: list[PlannedShot]) -> None:
    for prev, cur in zip(shots, shots[1:]):
        if cur.shot_size == prev.shot_size:
            cur.shot_size = kb.alt_size_for(cur.shot_size, cur.purpose)


def _enforce_budget(shots: list[PlannedShot], budget: int) -> list[PlannedShot]:
    """Trim to the shot budget by dropping the lowest-value NON-dialogue beats
    first; a shot that carries a line is never dropped."""
    if len(shots) <= budget:
        return shots
    kept = [s for s in shots if s.covers_lines]           # dialogue-bearing: protected
    extras = [s for s in shots if not s.covers_lines]     # silent beats: droppable
    room = max(0, budget - len(kept))
    return _in_order(shots, set(id(s) for s in kept) | set(id(s) for s in extras[:room]))


def _in_order(original: list[PlannedShot], keep_ids: set[int]) -> list[PlannedShot]:
    return [s for s in original if id(s) in keep_ids]


def _enforce_sanity(shots: list[PlannedShot]) -> None:
    for s in shots:
        if kb.is_incompatible(s.shot_size, s.lens):
            s.lens = kb.SHOT_PURPOSES.get(s.purpose, {}).get("lens", "50mm")
            if kb.is_incompatible(s.shot_size, s.lens):
                s.shot_size = (kb.SHOT_PURPOSES.get(s.purpose, {}).get("sizes") or ["MS"])[0]


def apply_guardrails(shots: list[PlannedShot], n_lines: int, budget: int) -> ShotPlan:
    shots = list(shots)
    _enforce_coverage(shots, n_lines)
    shots = _enforce_budget(shots, budget)
    _enforce_coverage(shots, n_lines)   # re-check: budget trim never drops a line, but keep the invariant explicit
    _enforce_no_repeat(shots)
    _enforce_sanity(shots)
    return ShotPlan(shots=shots)
