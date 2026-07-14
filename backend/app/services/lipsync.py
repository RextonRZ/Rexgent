"""Dialogue line -> shot mapping — pure functions, no I/O.

The k-th dialogue line of a scene belongs to the scene's k-th speaking shot,
and overflow lines fold onto the LAST speaking shot. HappyHorse native-talk
reads the picked line to name the on-camera speaker (the model speaks the words
itself and syncs its own mouth); no audio is sent to any model.
"""


def _norm_line(s):
    import re
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).strip()


def pick_lipsync_line(shot_id, speaking_shot_ids: list, lines: list[dict],
                      shot_dialogue: str | None = None) -> dict | None:
    """The single line this shot speaks. Prefer a CONTENT match on the shot's own
    dialogue (the storyboard can reorder lines across shots); fall back to the
    positional convention when no dialogue/text is available."""
    if shot_id not in speaking_shot_ids:
        return None
    if shot_dialogue:
        want = _norm_line(shot_dialogue)
        for ln in lines:
            if want and _norm_line(ln.get("text")) == want:
                return ln
        for ln in lines:  # partial: one contains the other (truncation-safe)
            t = _norm_line(ln.get("text"))
            if t and want and (t in want or want in t):
                return ln
    idx = speaking_shot_ids.index(shot_id)
    if idx >= len(lines):
        return None
    is_last = idx == len(speaking_shot_ids) - 1
    if is_last and len(lines) > len(speaking_shot_ids):
        return None  # folded overflow: this shot carries several lines
    return lines[idx]
