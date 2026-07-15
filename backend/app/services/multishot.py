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


def group_beats(shots: list, max_shots: int, wan_primary: bool = False,
                prev_cast: set | None = None) -> list[list]:
    """Group a scene's ordered shots into beats. Legacy (wan_primary=False):
    a beat is 2..max_shots consecutive DIALOGUE shots with combined cast <= 2 —
    one Wan multi-shot conversation. wan_primary=True: a beat is 2..max_shots
    consecutive SILENT shots that introduce NO new face (scenery or continuation
    of established faces) — one Wan visual multi-shot. Talking / new-face shots
    stay singletons (they route to HappyHorse). Non-qualifying shots become
    singleton groups, so the output flattens back to the input."""
    if not wan_primary:
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
    # wan_primary silent mode:
    groups: list[list] = []
    i, n = 0, len(shots)
    running = set(prev_cast or set())   # cast established BEFORE this shot
    while i < n:
        s = shots[i]
        # seed a beat on a SILENT shot that introduces no face absent from `running`
        if not _has_dialogue(s) and not (_chars(s) - running):
            run = [s]
            cast = set(_chars(s)) | set(running)
            j = i + 1
            while (j < n and len(run) < max_shots and not _has_dialogue(shots[j])
                   and not (_chars(shots[j]) - cast)):
                run.append(shots[j]); cast |= _chars(shots[j]); j += 1
            if len(run) >= 2:
                groups.append(run)
                running = _chars(run[-1]) or running
                i += len(run)
                continue
        groups.append([s])
        running = _chars(s) or running
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


def multishot_prompt(shots: list, durations: list | None = None) -> str:
    """One Wan multi-shot prompt in the Alibaba formula: an overall line, then a
    timecoded shot per line. 2.7 multi-shot is prompt-driven, so the sequence
    lives in the text."""
    durs = durations or [getattr(s, "estimated_duration_seconds", 5) or 5 for s in shots]
    t, lines = 0.0, []
    for k, s in enumerate(shots, 1):
        angle = getattr(s, "shot_type", None) or "shot"
        action = (getattr(s, "action", None) or "").strip()
        d = float(durs[k - 1]) if k - 1 < len(durs) else 5.0
        lines.append(f"Shot {k} [{round(t, 1)}-{round(t + d, 1)}s] ({angle}): {action}")
        t += d
    return ("One continuous sequence, the same location and lighting throughout, "
            "cutting between shots in order:\n" + "\n".join(lines))
