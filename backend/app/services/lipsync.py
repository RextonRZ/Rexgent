"""Wan lip-sync eligibility — pure functions, no I/O.

A shot may be lip-synced (wan `first_frame + driving_audio`) only when it
speaks EXACTLY one line and the speaker is the only visible face. The line
mapping follows the same convention `place_dialogue` uses: the k-th dialogue
line of a scene belongs to the scene's k-th speaking shot, and overflow lines
fold onto the LAST speaking shot — which therefore never lip-syncs.
"""


def pick_lipsync_line(shot_id, speaking_shot_ids: list, lines: list[dict]) -> dict | None:
    """The single line this shot speaks, or None when it has none / has many."""
    if shot_id not in speaking_shot_ids:
        return None
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
