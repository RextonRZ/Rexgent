import json

from app.director import knowledge_base as kb
from app.director.types import LookProfile, PlannedShot, ShotPlan
from app.services.prompt_loader import load_prompt
from app.services.qwen_client import QwenClient


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


_PLAN_PROMPT = None


def _plan_prompt() -> str:
    global _PLAN_PROMPT
    if _PLAN_PROMPT is None:
        _PLAN_PROMPT = load_prompt("director_plan.txt")
    return _PLAN_PROMPT


def _parse_plan(raw) -> list[PlannedShot]:
    out: list[PlannedShot] = []
    for d in QwenClient.as_list(raw):
        if not isinstance(d, dict):
            continue
        try:
            out.append(PlannedShot(
                purpose=str(d.get("purpose") or "dialogue"),
                shot_size=str(d.get("shot_size") or "MS"),
                camera_movement=str(d.get("camera_movement") or "STATIC"),
                lens=str(d.get("lens") or "50mm"),
                composition=str(d.get("composition") or "rule_of_thirds"),
                intended_duration=float(d.get("intended_duration") or 5.0),
                covers_lines=[int(i) for i in (d.get("covers_lines") or []) if isinstance(i, (int, float))],
                action_beat=str(d.get("action_beat") or "a beat"),
                blocking_delta=(str(d["blocking_delta"]) if d.get("blocking_delta") else None),
                # per-shot Wan effect: honored only if it's a known special-effect term
                special_effect=(str(d["special_effect"])
                                if kb.is_special_effect(d.get("special_effect")) else None),
            ))
        except (TypeError, ValueError):
            continue
    return out


async def plan_scene(scene: dict, cast: list[dict], look: LookProfile,
                     budget: int, qwen) -> ShotPlan:
    """Plan a scene's shots: LLM cinematic intent, then deterministic guardrails.
    Never raises — a failed/empty LLM plan still yields a coverage-complete plan."""
    lines = scene.get("dialogue") or []
    n_lines = len(lines)
    user = (
        f"Scene:\n{json.dumps(scene, ensure_ascii=False)}\n\n"
        f"Cast: {json.dumps([c.get('name') for c in cast], ensure_ascii=False)}\n\n"
        f"Look: lighting={look.lighting}, colour={look.colour_mood}, "
        f"lens_bias={look.lens_bias}, pace={look.camera_pace}\n\n"
        f"Shot budget: at most {budget} shots. There are {n_lines} dialogue line(s) "
        f"(0-based indices 0..{max(0, n_lines - 1)})."
    )
    try:
        raw = await qwen.chat_json(
            messages=[{"role": "system", "content": _plan_prompt()},
                      {"role": "user", "content": user}],
            temperature=0.7, task="director_plan")
        shots = _parse_plan(raw)
    except Exception:  # noqa: BLE001 — planning is best-effort; guardrails backfill
        shots = []
    plan = apply_guardrails(shots, n_lines=n_lines, budget=budget)
    for s in plan.shots:
        # scene-wide look attributes flow onto every shot (special_effect stays per-shot)
        s.light_quality = look.light_quality
        s.stylization = look.stylization
    return plan
