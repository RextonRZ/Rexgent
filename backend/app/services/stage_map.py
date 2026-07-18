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


import re

_FLAT_KEY_RE = re.compile(
    r"\b(character_name|frame_position|screen_side|facing|posture|eyeline|action)\s*[:=]",
    re.IGNORECASE)
_GEOMETRY_KEYS = ("frame_position", "screen_side", "facing", "posture", "eyeline", "action")


def _parse_flat_subject(text: str) -> dict | None:
    """A worse drift than bare names: the WHOLE subject flattened into one
    string. Two shapes observed in production:
    - 'character_name: IM SOL, frame_position: FG, screen_side: left, ...'
      (split on known key markers, never commas — values contain commas)
    - a JSON object AS a string, '{"character": "CATHERINE", ...}' — the
      quote between key and colon defeats the marker regex, so try a real
      JSON parse first.
    None when neither shape applies."""
    text = text.strip()
    if text.startswith("{"):
        try:
            import json
            obj = json.loads(text)
            if isinstance(obj, dict):
                out = {("character" if k == "character_name" else k): v
                       for k, v in obj.items() if v}
                return out or None
        except (ValueError, TypeError):
            pass
    marks = list(_FLAT_KEY_RE.finditer(text))
    if not marks:
        return None
    out: dict = {}
    # the character name leads (e.g. "ANNA: frame_position=..."); drop its
    # trailing colon along with separators
    lead = text[: marks[0].start()].strip(" ,;:")
    if lead:
        out["character"] = lead
    for mark, nxt in zip(marks, list(marks[1:]) + [None]):
        key = mark.group(1).lower()
        val = text[mark.end(): nxt.start() if nxt else len(text)].strip(" ,;")
        if val:
            out["character" if key == "character_name" else key] = val
    return out or None


def normalize_subjects(raw) -> list | None:
    """LLM output drifts: `subjects` sometimes arrives as bare name strings,
    as whole subjects flattened into one string, or as junk instead of the
    structured dicts the schema asks for. Keep real dicts, un-flatten
    flattened strings (including geometry trapped inside a dict's own
    `character` value), coerce plain names to {'character': name}, drop
    everything else. None when nothing usable remains."""
    if not isinstance(raw, list):
        return None
    out = []
    for s in raw:
        if isinstance(s, dict):
            flat = None
            if not any(k in s for k in _GEOMETRY_KEYS):
                flat = _parse_flat_subject(str(s.get("character") or ""))
            out.append({**s, **flat} if flat else s)
        elif isinstance(s, str) and s.strip():
            out.append(_parse_flat_subject(s.strip()) or {"character": s.strip()})
    return out or None


_NAME_STOPWORDS = {"THE", "AND", "HIS", "HER", "VON", "VAN", "DER", "MAN", "WOMAN"}


def _name_in_text(name: str, text: str) -> bool:
    """Is this character named in the text? Full name on a word boundary, else
    any distinctive name token (>=3 chars, not a stopword). A name that is ITSELF
    a single common noun ('Man', 'Woman') can never be matched in prose without
    false positives, so only a real subject entry keeps such a character in
    frame — the word 'man' in the action does not."""
    up = (text or "").upper()
    full = str(name or "").strip().upper()
    if not full or not up:
        return False
    toks = re.split(r"[\s-]+", full)
    if len(toks) == 1 and full in _NAME_STOPWORDS:
        return False
    if re.search(r"\b" + re.escape(full) + r"\b", up):
        return True
    distinctive = [t for t in toks if len(t) >= 3 and t not in _NAME_STOPWORDS]
    return any(re.search(r"\b" + re.escape(t) + r"\b", up) for t in distinctive)


def reconcile_frame_with_subjects(in_frame: list, subjects, action: str) -> list:
    """Drop a character listed in `characters_in_frame` who has NO blocking
    subject AND is not named in the `action` — a spurious inclusion the stager
    never placed (the antagonist literally named 'Man' appearing in a two-person
    beat he is not part of). Such a character has no position, yet the render
    would still send their plate as a face reference and the model floats them
    in at random. Order preserved.

    Only applies when SOME subjects exist: a shot with no blocking at all is a
    different case (the diagram shows 'no geometry'), so its cast is left intact.
    A character is kept when they have a subject OR are named in the action."""
    subs = [s for s in (subjects or []) if isinstance(s, dict)]
    if not subs:
        return list(in_frame or [])
    subj_names = {str(s.get("character") or "").strip().upper() for s in subs}
    return [n for n in (in_frame or [])
            if str(n).strip().upper() in subj_names or _name_in_text(n, action)]


_MOVE_RE = re.compile(
    r"\b(walk|walks|walking|step|steps|stepping|move|moves|moving|approach|"
    r"approaches|approaching|cross|crosses|crossing|closer|away|toward|"
    r"towards|retreat|retreats|backs?|backing|rush|rushes|rushing|"
    r"lean|leans|leaning|rise|rises|rising|sits?|sitting|stands? up)\b", re.IGNORECASE)


_RELEASE_RE = re.compile(
    r"\b(?:puts?|sets?|lays?|places?)\s+(?:\w+\s+){0,3}?(?:down|aside|away)\b"
    r"|\blets?\s+go\b"
    r"|\bhands?\s+(?:\w+\s+){1,4}?to\b",
    re.IGNORECASE)


def thread_held_objects(shots_blocking: list) -> tuple[list, list[str]]:
    """A prop a character CARRIES (a birdcage, a phone, a letter) must stay in
    hand across a scene's shots, but held state lived only in each shot's
    free-text action - so a later shot that did not restate it dropped the
    object (the birdcage vanished between two consecutive shots). Thread it
    deterministically, mirroring enforce_scene_sides: once a character holds
    something, stamp `holding` onto that character in every later shot until
    they name a new object or visibly release it (set it down, hand it off).

    Mutates the subject dicts in place, returns (the same list, notes)."""
    held: dict[str, str] = {}
    notes: list[str] = []
    for i, blocking in enumerate(shots_blocking):
        if not blocking or not blocking.get("subjects"):
            continue
        for s in blocking["subjects"]:
            if not isinstance(s, dict):
                continue  # defense in depth - normalize_subjects upstream
            name = str(s.get("character") or "").strip().upper()
            if not name:
                continue
            own = s.get("holding")
            has_obj = own is not None and str(own).strip() != ""
            released = bool(_RELEASE_RE.search(str(s.get("action") or "")))
            if has_obj:
                # the board named a held object this shot: it wins and carries on
                held[name] = str(own).strip()
            elif released:
                # visibly set down or handed off: stop carrying it forward
                held.pop(name, None)
            elif name in held:
                # the board omitted it but the character was carrying something -
                # restore it so the object does not vanish between cuts
                s["holding"] = held[name]
                notes.append(
                    f"shot {i + 1}: {s.get('character')} still holding "
                    f"{held[name]} (restored, board omitted it)")
    return shots_blocking, notes


_APPROACH_VERBS = (r"(?:walks?|walking|runs?|running|steps?|stepping|moves?|"
                   r"moving|goes|going|comes?|coming|rushes?|rushing|"
                   r"hurries|hurrying)")
_AWAY_RE = re.compile(
    r"\b(?:walks?|steps?|turns?|moves?|backs?|pulls?)\s+(?:\w+\s+){0,2}?away\b"
    r"|\bleaves\b|\bexits?\b|\bstorms?\s+(?:off|out)\b", re.IGNORECASE)


def _approach_re(name: str) -> re.Pattern:
    """An approach aimed at THIS partner by name: 'walks over to Leo',
    'runs toward LEO', 'approaches Leo'. Name-gated so 'walks to the
    window' never matches."""
    nm = re.escape(name)
    return re.compile(
        rf"\b(?:{_APPROACH_VERBS}\s+(?:back\s+)?(?:over\s+|up\s+)?"
        rf"(?:to|toward|towards)|approach(?:es|ing)?)\s+(?:the\s+)?({nm})\b",
        re.IGNORECASE)


def enforce_proximity(shots: list) -> tuple[list, list[str]]:
    """You cannot walk toward someone you are already with. Two characters
    sharing a shot are TOGETHER; while together, a later shot's action that
    approaches the partner by name ('Angeline walks over to Leo') is a
    teleport-reset the board wrote by accident — rewrite the approach to
    'stands with <partner>' in both the shot action and the subject action.
    A visible separation (walks away, leaves, exits) breaks the pair, after
    which a fresh approach is legitimate staging again.

    Operates on the storyboard's own shot dicts (action + subjects), mutates
    in place, returns (the same list, notes) - mirrors the other passes."""
    together: set[frozenset] = set()
    notes: list[str] = []

    def _partners(name_u: str) -> list[str]:
        return [n for pair in together if name_u in pair
                for n in pair if n != name_u]

    def _rewrite(text: str, partner_u: str, where: str, i: int) -> str:
        # try the full partner name, then its distinctive tokens
        candidates = [partner_u] + [t for t in re.split(r"[\s-]+", partner_u)
                                    if len(t) >= 3 and t not in _NAME_STOPWORDS]
        for cand in candidates:
            m = _approach_re(cand).search(text)
            if m:
                notes.append(f"shot {i + 1}: approach toward {m.group(1)} but "
                             f"they are already together - rewritten to stand "
                             f"with them ({where})")
                return text[:m.start()] + f"stands with {m.group(1)}" + text[m.end():]
        return text

    for i, sd in enumerate(shots):
        if not isinstance(sd, dict):
            continue
        subs = [s for s in (sd.get("subjects") or []) if isinstance(s, dict)]
        names_u = [str(s.get("character") or "").strip().upper() for s in subs]
        names_u = [n for n in names_u if n]
        # (1) approaches toward an ALREADY-together partner get rewritten
        for s, name_u in zip(subs, names_u):
            act = str(s.get("action") or "")
            for partner_u in _partners(name_u):
                new = _rewrite(act, partner_u, "subject", i)
                if new != act:
                    s["action"] = act = new
        shot_act = str(sd.get("action") or "")
        for pair in list(together):
            for partner_u in pair:
                new = _rewrite(shot_act, partner_u, "action", i)
                if new != shot_act:
                    sd["action"] = shot_act = new
        # (2) sharing this shot establishes togetherness (at the cut they
        # are in one framing - the next shot may not re-approach)
        for a in range(len(names_u)):
            for b in range(a + 1, len(names_u)):
                together.add(frozenset({names_u[a], names_u[b]}))
        # (3) a visible separation breaks every pair the mover is in
        for s, name_u in zip(subs, names_u):
            texts = f"{s.get('action') or ''} {shot_act}"
            if _AWAY_RE.search(texts):
                together = {p for p in together if name_u not in p}
    return shots, notes


def enforce_scene_sides(shots_blocking: list) -> tuple[list, list[str]]:
    """shots_blocking: per shot, {"subjects": [...], "reverse_angle": bool}
    or None for shots without blocking. Mutates screen_side AND frame_position
    in place on violations. Returns (the same list, correction notes).

    Two properties carry across the scene: the 180-degree rule (screen side)
    and DEPTH (frame_position) — a pair standing close in one shot teleported
    across the room in the next. Depth may only change when the subject's own
    `action` moves them; otherwise it snaps back to the established depth."""
    established: dict[str, str] = {}
    depths: dict[str, str] = {}
    notes: list[str] = []
    for i, blocking in enumerate(shots_blocking):
        if not blocking or not blocking.get("subjects"):
            continue
        if blocking.get("reverse_angle"):
            # a deliberate reverse crosses the line: everyone re-establishes
            established = {}
        proposed: dict[str, str] = {}
        for s in blocking["subjects"]:
            if not isinstance(s, dict):
                continue  # defense in depth — normalize_subjects upstream
            name = str(s.get("character") or "").strip().upper()
            if not name:
                continue
            side = s.get("screen_side")
            if side in ("left", "center", "right"):
                proposed[name] = side
                held = established.get(name)
                if held and {side, held} == {"left", "right"}:
                    s["screen_side"] = held
                    notes.append(
                        f"shot {i + 1}: {name} drifted to {side}, snapped back to {held}")
                elif not held and side in ("left", "right"):
                    established[name] = side
            pos = str(s.get("frame_position") or "").strip().upper()
            if pos in ("FG", "MG", "BG"):
                moved = bool(_MOVE_RE.search(str(s.get("action") or "")))
                held_pos = depths.get(name)
                if held_pos and pos != held_pos and not moved:
                    s["frame_position"] = held_pos
                    notes.append(
                        f"shot {i + 1}: {name} jumped {held_pos}->{pos} with no "
                        f"movement written, snapped back to {held_pos}")
                else:
                    depths[name] = pos
        # Two subjects can never share a lateral side in ONE shot (they render
        # stacked on each other and the eyelines stop making sense). The usual
        # cause: a side established beside one scene partner, then the pairing
        # CHANGED and the snap dragged the character on top of the new partner.
        # The fresh pairing wins: the snapped character re-establishes on the
        # side this shot's board actually asked for.
        for side in ("left", "right"):
            group = [s for s in blocking["subjects"] if isinstance(s, dict)
                     and s.get("screen_side") == side
                     and str(s.get("character") or "").strip()]
            if len(group) < 2:
                continue
            other = "right" if side == "left" else "left"
            other_taken = any(isinstance(s, dict) and s.get("screen_side") == other
                              for s in blocking["subjects"])
            if other_taken:
                continue
            mover = next((s for s in group
                          if proposed.get(str(s.get("character")).strip().upper()) == other),
                         group[-1])
            name = str(mover.get("character")).strip().upper()
            mover["screen_side"] = other
            established[name] = other
            notes.append(
                f"shot {i + 1}: two subjects shared screen-{side}; "
                f"{name} re-established at screen-{other}")
    return shots_blocking, notes
