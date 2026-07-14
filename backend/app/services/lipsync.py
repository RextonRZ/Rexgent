"""Wan lip-sync eligibility — pure functions, no I/O.

A shot may be lip-synced (wan `first_frame + driving_audio`) only when it
speaks EXACTLY one line and the speaker is the only visible face. The line
mapping follows the same convention `place_dialogue` uses: the k-th dialogue
line of a scene belongs to the scene's k-th speaking shot, and overflow lines
fold onto the LAST speaking shot — which therefore never lip-syncs.
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


def speaker_matches(line: dict, in_frame: list, foreground: list) -> bool:
    """True when the line's speaker is the ONLY non-occluded face in frame."""
    fg = {str(n).strip().upper() for n in (foreground or [])}
    visible = [str(n).strip().upper() for n in (in_frame or [])
               if str(n).strip().upper() not in fg]
    speaker = str(line.get("character_name") or "").strip().upper()
    return len(visible) == 1 and bool(speaker) and visible[0] == speaker


def lipsync_media(anchor_url: str, audio_url: str) -> list[dict]:
    """The wan2.7-i2v media payload: continue from the frame, drive the mouth."""
    return [
        {"type": "first_frame", "url": anchor_url},
        {"type": "driving_audio", "url": audio_url},
    ]
