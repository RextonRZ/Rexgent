"""Per-scene stage map: the 180-degree rule, enforced deterministically.

The storyboard prompt ASKS the model to keep every character on their
established screen side, but a request is not a guarantee — one drifting shot
flips the geography and consecutive shots stop cutting together. This module
walks a scene's shots in order AFTER boarding: a character's first left/right
placement establishes their side, later left<->right flips are snapped back,
and a shot flagged `reverse_angle` legitimately re-establishes everyone.

Center is neutral: moving to center (a dolly-in single, a walk-through) is
never a violation and never re-establishes a side.
"""


def enforce_scene_sides(shots_blocking: list) -> tuple[list, list[str]]:
    """shots_blocking: per shot, {"subjects": [...], "reverse_angle": bool}
    or None for shots without blocking. Mutates screen_side in place on
    violations. Returns (the same list, human-readable correction notes)."""
    established: dict[str, str] = {}
    notes: list[str] = []
    for i, blocking in enumerate(shots_blocking):
        if not blocking or not blocking.get("subjects"):
            continue
        if blocking.get("reverse_angle"):
            # a deliberate reverse crosses the line: everyone re-establishes
            established = {}
        for s in blocking["subjects"]:
            name = str(s.get("character") or "").strip().upper()
            side = s.get("screen_side")
            if not name or side not in ("left", "center", "right"):
                continue
            held = established.get(name)
            if held and {side, held} == {"left", "right"}:
                s["screen_side"] = held
                notes.append(
                    f"shot {i + 1}: {name} drifted to {side}, snapped back to {held}")
            elif not held and side in ("left", "right"):
                established[name] = side
    return shots_blocking, notes
