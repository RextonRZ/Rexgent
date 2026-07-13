"""Pure logic for multi-shot conversation beats. No I/O.

A BEAT is a run of consecutive dialogue shots in one scene involving at most two
distinct on-screen characters — a back-and-forth that wan2.7's multi-shot mode
can render as ONE clip with the faces locked across the angle cuts. Everything
else stays a singleton (rendered per shot as today).
"""


def _has_dialogue(shot) -> bool:
    return bool((getattr(shot, "dialogue", None) or "").strip())


def _chars(shot) -> set:
    return {str(c) for c in (getattr(shot, "characters_in_frame", None) or [])}


def group_beats(shots: list, max_shots: int) -> list[list]:
    """Group a scene's ordered shots into beats. A beat is 2..max_shots
    consecutive dialogue shots whose combined cast is <= 2 people. Non-qualifying
    shots become singleton groups, so the output flattens back to the input."""
    groups: list[list] = []
    i, n = 0, len(shots)
    while i < n:
        run = [shots[i]]
        cast = _chars(shots[i])
        if _has_dialogue(shots[i]):
            j = i + 1
            while (j < n and len(run) < max_shots and _has_dialogue(shots[j])
                   and len(cast | _chars(shots[j])) <= 2):
                run.append(shots[j])
                cast |= _chars(shots[j])
                j += 1
        if len(run) >= 2:
            groups.append(run)
            i += len(run)
        else:
            groups.append([shots[i]])
            i += 1
    return groups


def slice_ranges(durations: list, total: float) -> list[tuple]:
    """Per-shot (start, end) offsets inside the merged clip of length `total`,
    proportional to each shot's duration. Contiguous; the last slice ends exactly
    at `total` so no footage is lost to rounding."""
    span = float(sum(durations)) or 1.0
    ranges, acc = [], 0.0
    for k, d in enumerate(durations):
        start = round(acc / span * total, 3)
        acc += float(d)
        end = total if k == len(durations) - 1 else round(acc / span * total, 3)
        ranges.append((start, round(end, 3)))
    return ranges


def multishot_prompt(shots: list) -> str:
    """One wan2.7 multi-shot prompt describing the beat as a continuous exchange
    cutting between angles. 2.7 multi-shot is prompt-driven, so the sequence lives
    in the text."""
    lines = []
    for k, s in enumerate(shots, 1):
        angle = getattr(s, "shot_type", None) or "shot"
        action = (getattr(s, "action", None) or "").strip()
        lines.append(f"Shot {k} ({angle}): {action}")
    return ("A continuous conversation between the same characters, one unbroken "
            "scene cutting between camera angles in order:\n" + "\n".join(lines))
