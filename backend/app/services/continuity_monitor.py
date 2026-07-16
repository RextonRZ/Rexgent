"""Deterministic continuity checks on a boarded scene — pure, no I/O, WARNING
only (mirrors extras_monitor): the break is surfaced, never blocked or
auto-fixed. Only the RELIABLY detectable subset lives here; the fuzzy
continuity rules (state threading, introduce-before-use, arrival beats) are
enforced prompt-side in director_plan / storyboard_stage / storyboard_generate.

Checks:
  hanging_question - a line ending in '?' (or trailing off) immediately
      followed by a people-free scenery shot: the answer got split from its
      question and the conversation loses continuity.
  repeated_action  - two shots in one scene with identical action text: each
      clip renders independently, so the finished cut re-stages the same
      instant (the character resets and winds up again).
  frozen_beat      - consecutive shots with identical emotional_beat text: no
      emotional progression between cuts.
"""
import re

_WS_RE = re.compile(r"\s+")


def _norm(text) -> str:
    return _WS_RE.sub(" ", str(text or "").strip().lower())


def detect_continuity_breaks(shots: list[dict]) -> list[dict]:
    """Scan one scene's ordered shot dicts (shot_number, action, dialogue,
    characters_in_frame, emotional_beat). Returns [{type, shot_number,
    warning}] — empty when the scene reads continuously."""
    findings: list[dict] = []
    seen_actions: dict[str, int] = {}
    prev: dict | None = None
    for i, sh in enumerate(shots or []):
        num = sh.get("shot_number") or i + 1
        # a question must not be answered by scenery
        if prev is not None:
            prev_line = str(prev.get("dialogue") or "").rstrip()
            faceless = not (sh.get("characters_in_frame") or [])
            if faceless and prev_line.endswith(("?", "...", "…")):
                findings.append({
                    "type": "hanging_question", "shot_number": num,
                    "warning": (f"shot {num} cuts to people-free scenery right "
                                f"after the line {prev_line[-60:]!r} — the answer "
                                "is split from its question")})
        # the same instant must never be re-staged
        act = _norm(sh.get("action"))
        if act:
            if act in seen_actions:
                findings.append({
                    "type": "repeated_action", "shot_number": num,
                    "warning": (f"shot {num} repeats shot {seen_actions[act]}'s "
                                f"action verbatim ({str(sh.get('action'))[:70]!r}) — "
                                "each clip renders independently, so the cut "
                                "re-stages the same instant")})
            else:
                seen_actions[act] = num
        # the audience's feeling must move between cuts
        if prev is not None:
            beat, prev_beat = _norm(sh.get("emotional_beat")), _norm(prev.get("emotional_beat"))
            if beat and beat == prev_beat:
                findings.append({
                    "type": "frozen_beat", "shot_number": num,
                    "warning": (f"shots {prev.get('shot_number') or i} and {num} "
                                f"share the emotional beat {str(sh.get('emotional_beat'))[:50]!r} — "
                                "no progression between cuts")})
        prev = sh
    return findings
