"""Recurring-extra detection — pure functions, no I/O.

script_generate's rule: an UNNAMED presence (a shadowy figure, a silhouette)
may appear ONCE; a figure that recurs must be promoted to cast (named + plated)
or it renders as a DIFFERENT person every shot, because nothing locks a look
onto a character that has no name. Nothing downstream enforced that rule — the
LLM could break it silently and the drama shipped with a shape-shifting extra.

This module DETECTS violations and returns warnings to surface. It never
blocks and never mutates — the same catch-and-flag pattern as stage_map.

Two signals:
1. a non-cast name listed in `characters_in_frame` (should never happen after
   board-time filtering; flagged on ANY occurrence as defense in depth);
2. the same generic figure phrase recurring across MORE THAN ONE shot or scene
   in action/notes text ("a shadowy figure" in shot 2, "the shadowy figure" in
   shot 5 — one presence, two independent renders, two different people).

A bare indefinite mention ("a man", "a woman") does NOT count — two of those
are usually two different passersby. A mention counts when it carries a
modifier ("a hooded man") or the definite article ("the man" — definiteness
implies an established referent). Cast members described generically in masked
action text can false-positive; these are warnings, not verdicts.
"""

import re

from app.services.guardrails import canonical_character

_FIGURE_NOUN = (
    "figure|silhouette|stranger|presence|shadow|man|woman|person|child|boy|girl|"
    "passerby|onlooker|patron|customer|guard|nurse|doctor|officer|cop|driver|"
    "waiter|waitress|bartender|neighbor|neighbour|vendor|beggar|monk|priest"
)
# article + up to two modifier words + a figure noun, e.g. "the shadowy figure",
# "a tall hooded man". Modifiers must be plain words (no digits/punctuation).
_FIGURE_RE = re.compile(
    rf"\b(the|a|an)\s+((?:[a-z][a-z-]*\s+){{0,2}})({_FIGURE_NOUN})\b",
    re.IGNORECASE)


def _figure_mentions(text: str) -> set[str]:
    """Normalized figure phrases in one shot's text. Key = modifiers + noun,
    lowercased ('shadowy figure'); bare indefinite nouns are skipped."""
    out: set[str] = set()
    for article, mods, noun in _FIGURE_RE.findall(text or ""):
        mods = re.sub(r"\s+", " ", mods).strip().lower()
        definite = article.lower() == "the"
        if not mods and not definite:
            continue  # "a man" alone: any passerby, not a recurring presence
        out.add(f"{mods} {noun.lower()}".strip())
    return out


def detect_recurring_extras(shots: list[dict], cast_names) -> list[dict]:
    """shots: ordered [{"scene_number", "shot_number", "action", "notes",
    "characters_in_frame"}, ...] across the whole script. Returns one warning
    dict per finding: {"figure", "shots" [(scene, shot)...], "scenes" [..],
    "warning" str}. Empty list when the board is clean."""
    cast = [str(n) for n in (cast_names or []) if str(n).strip()]
    cast_upper = {n.upper() for n in cast}
    findings: list[dict] = []

    # signal 1 — non-cast names in characters_in_frame
    by_name: dict[str, list] = {}
    for s in shots or []:
        where = (s.get("scene_number"), s.get("shot_number"))
        for n in (s.get("characters_in_frame") or []):
            resolved = canonical_character(str(n), cast)
            if str(resolved).upper() not in cast_upper:
                by_name.setdefault(str(n), []).append(where)
    for name, places in by_name.items():
        findings.append({
            "figure": name,
            "shots": places,
            "scenes": sorted({sc for sc, _ in places if sc is not None}),
            "warning": (f'"{name}" is listed in characters_in_frame but is not '
                        "in the cast — no plate locks this identity, so it "
                        "renders as a different person on every appearance"),
        })

    # signal 2 — the same generic figure phrase across >1 shot (or scene)
    by_figure: dict[str, list] = {}
    for s in shots or []:
        where = (s.get("scene_number"), s.get("shot_number"))
        text = f"{s.get('action') or ''} {s.get('notes') or ''}"
        for phrase in _figure_mentions(text):
            by_figure.setdefault(phrase, []).append(where)
    for phrase, places in sorted(by_figure.items()):
        if len(places) < 2:
            continue
        scenes = sorted({sc for sc, _ in places if sc is not None})
        findings.append({
            "figure": phrase,
            "shots": places,
            "scenes": scenes,
            "warning": (f'recurring extra never promoted to cast: "{phrase}" '
                        f"appears in {len(places)} shots"
                        + (f" across scenes {scenes}" if len(scenes) > 1 else "")
                        + " — an unnamed recurring figure renders as a "
                          "different person each time; give it a NAME in the "
                          "cast to lock a look"),
        })
    return findings
