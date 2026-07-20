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


def _mentions(token: str, text_up: str) -> bool:
    r"""Whole-token containment that works for BOTH Latin and CJK scripts. \b
    fails between Chinese characters — 抱着 and 雪球 are all \w with no boundary
    between them — which dropped a Chinese-named pet from the shots that name
    it. Forbid only ASCII word chars on either side: a Latin name still can't
    glue onto adjacent letters/digits ('Ann' inside 'Anna'), while a CJK name's
    neighbours are never ASCII word chars, so it matches run together in prose."""
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])",
                     text_up) is not None


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
    if _mentions(full, up):
        return True
    distinctive = [t for t in toks if len(t) >= 3 and t not in _NAME_STOPWORDS]
    return any(_mentions(t, up) for t in distinctive)


def cast_named_in_prose(scene_chars: list, all_cast: list, prose: str) -> list:
    """Add any project cast member NAMED in the scene's prose but missing from
    the structurer's per-scene list. The structurer drops an on-screen pet and
    object-like names (雪球 = 'snowball') from characters_present, and a bare \\b
    never matched a CJK name — so the pet never entered the scene's cast, was
    left out of every shot, and then the set dresser (not knowing it is a
    character) dressed it as a prop. Existing entries keep their order/dicts;
    found ones are appended in all_cast order. Matched CJK-safely against the
    prose (description + stage directions) ONLY — a character merely talked
    about in dialogue is not necessarily on screen."""
    present = {str((c or {}).get("name", "")).strip().upper()
               for c in (scene_chars or []) if isinstance(c, dict)}
    out = list(scene_chars or [])
    for c in (all_cast or []):
        if not isinstance(c, dict):
            continue
        nm = str(c.get("name") or "").strip()
        if nm and nm.upper() not in present and _name_in_text(nm, prose):
            out.append(c)
            present.add(nm.upper())
    return out


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


# zh alternations ride the same regexes with NO \b (CJK has no word
# boundaries): a zh drama's actions were invisible to every verb pattern, so
# legitimate movement was snapped back, held props never released, and pairs
# never separated.
_MOVE_RE = re.compile(
    r"\b(walk|walks|walking|step|steps|stepping|move|moves|moving|approach|"
    r"approaches|approaching|cross|crosses|crossing|closer|away|toward|"
    r"towards|retreat|retreats|backs?|backing|rush|rushes|rushing|"
    r"lean|leans|leaning|rise|rises|rising|sits?|sitting|stands? up)\b"
    r"|走|跑|奔|冲过|移动|靠近|远离|后退|退后|上前|起身|站起|坐下|蹲下|"
    r"跪下|翻过|爬|越过|跨过|穿过|挪", re.IGNORECASE)


_RELEASE_RE = re.compile(
    r"\b(?:puts?|sets?|lays?|places?)\s+(?:\w+\s+){0,3}?(?:down|aside|away)\b"
    r"|\blets?\s+go\b"
    r"|\bhands?\s+(?:\w+\s+){1,4}?to\b"
    r"|放下|放开|松开|搁下|递给|交给|放到|放进|塞给",
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


# A tie to a fixed anchor (a rope to a tree). The tie lived only in one shot's
# prose, so later shots rendered the rope lying unattached and the collar
# flickering — thread it like held props, and print it in every blocking row.
_TETHER_RELEASE_RE = re.compile(
    r"抱起|抱走|解开|松开|放开|挣脱|挣开"
    r"|\b(?:picks?\s+up|unties?|unleash(?:es)?|frees?|releases?)\b",
    re.IGNORECASE)


def _tether_re(name: str) -> re.Pattern:
    """NAME 被拴在 X / NAME is tied to the X — the anchor captured."""
    nm = re.escape(name)
    return re.compile(
        rf"{nm}被?[拴绑系]在([^，。！？\s]{{1,10}})"
        rf"|{nm}\s+(?:is\s+|was\s+)?(?:tied|leashed|chained|tethered)\s+"
        rf"(?:to|at)\s+(?:the\s+|a\s+)?([\w'-]+)",
        re.IGNORECASE)


def thread_tethered(shots: list) -> tuple[list, list[str]]:
    """Once a character (usually a pet) is TIED to an anchor, stamp `tethered`
    onto their subject in every shot until a visible release (picked up,
    untied, breaks free). The blocking row then states the leash per shot, so
    the rope stays attached to the collar instead of lying on the ground.
    Mutates subject dicts in place, returns (shots, notes)."""
    tied: dict[str, str] = {}
    notes: list[str] = []
    for i, sd in enumerate(shots):
        if not isinstance(sd, dict):
            continue
        action = str(sd.get("action") or "")
        subs = [s for s in (sd.get("subjects") or []) if isinstance(s, dict)]
        for s in subs:
            nm = str(s.get("character") or "").strip()
            if not nm:
                continue
            m = _tether_re(nm).search(action)
            if m:
                anchor = (m.group(1) or m.group(2) or "").strip()
                if anchor:
                    tied[nm.upper()] = anchor
            elif (nm.upper() in tied
                  and _TETHER_RELEASE_RE.search(action)
                  and _mentions(nm.upper(), action.upper())):
                # released in THIS shot's action (抱起雪球 / picks Snowy up)
                tied.pop(nm.upper(), None)
        for s in subs:
            nm = str(s.get("character") or "").strip().upper()
            if nm in tied:
                s["tethered"] = f"拴在{tied[nm]}" if re.search(
                    r"[一-鿿]", tied[nm]) else f"tied to the {tied[nm]}"
                notes.append(f"shot {i + 1}: {s.get('character')} stays "
                             f"tethered ({s['tethered']})")
    return shots, notes


# WORLD position: camera-relative blocking (MG, screen-right) is satisfied by
# many spots in the room — 玛丽 "midground right" renders inside OR outside the
# fence at the model's whim. An anchor stated in the prose (站在花园外, stands
# by the gate) threads across the scene like held props and is restated in
# every blocking row, so renders stop relocating people between shots.
_ANCHOR_ZH = re.compile(
    r"(?:站在|坐在|蹲在|跪在|靠在|停在|留在|守在|躲在|走到|跑到|来到|回到|冲到|奔到)"
    r"([^，。！？\s]{1,10})")
_ANCHOR_EN_STAND = (r"\b(?:stands?|sits?|waits?|stays?|remains?|leans?|"
                    r"kneels?|crouch(?:es)?)\s+"
                    r"(?:at|by|beside|near|outside|inside|behind|in\s+front\s+of)\s+"
                    r"(?:the\s+|a\s+|an\s+)?([\w'-]+(?:\s[\w'-]+)?)")
_ANCHOR_EN_MOVE = (r"\b(?:walks?|runs?|comes?|returns?|goes|moves?|rushes?)\s+"
                   r"(?:back\s+)?to\s+(?:the\s+|a\s+)?([\w'-]+(?:\s[\w'-]+)?)")


def _anchor_res(name: str) -> list[re.Pattern]:
    nm = re.escape(name)
    return [
        re.compile(rf"{nm}[^，。！？]{{0,4}}?{_ANCHOR_ZH.pattern}"),
        re.compile(rf"{nm}[^.!?]{{0,20}}?{_ANCHOR_EN_STAND}", re.IGNORECASE),
        re.compile(rf"{nm}[^.!?]{{0,20}}?{_ANCHOR_EN_MOVE}", re.IGNORECASE),
    ]


# A "place" that is actually another clause's leftovers: 一起/这里/那里/原地/
# 一旁/一边 are positions relative to someone, not landmarks, and a capture
# containing 什么/哪 means the gap ran past the place into a trailing question
# ("花园外做什么").
_ANCHOR_STOPLIST = {"一起", "这里", "那里", "原地", "一旁", "一边"}


def _place_is_bogus(place: str) -> bool:
    return place in _ANCHOR_STOPLIST or "什么" in place or "哪" in place


def _crosses_other_subject(match_text: str, nm: str, other_names: list) -> bool:
    """The matched span bridged into another subject's clause ('玛丽问安吉琳
    站在...' anchoring 玛丽 at Angeline's spot) or the 'place' captured is
    itself a person ('站在安吉琳身旁' — a person is not a landmark)."""
    return any(other and other != nm and other in match_text
               for other in other_names)


# A departure means the character is mid-motion AWAY from their anchor, not
# arriving somewhere new — 转身离开/走向大门 must CLEAR the stale anchor
# instead of re-anchoring to the destination named in the same breath.
_ANCHOR_CLEAR_ZH = r"走向|跑向|冲向|奔向|走出|跑出|冲出|离开|转身离"
_ANCHOR_CLEAR_EN = (r"\b(?:walks?|runs?|storms?|heads?)\s+(?:away|off|out)\b"
                    r"|\b(?:leaves?|exits?)\b")


def _anchor_clear_res(name: str) -> list[re.Pattern]:
    nm = re.escape(name)
    return [
        re.compile(rf"{nm}[^，。！？]{{0,4}}?(?:{_ANCHOR_CLEAR_ZH})"),
        re.compile(rf"{nm}[^.!?]{{0,20}}?(?:{_ANCHOR_CLEAR_EN})", re.IGNORECASE),
    ]


def thread_anchors(shots: list) -> tuple[list, list[str]]:
    """Stamp each subject's WORLD anchor (站在花园外 / stands by the gate)
    onto their blocking in every shot until the prose moves them somewhere
    else. A departure (转身离开, walks off) CLEARS the anchor instead of
    re-anchoring to wherever they are headed - checked BEFORE this shot's own
    establish patterns, so "转身离开，走到门口" still re-anchors at the new
    spot within the same shot. Scene-scoped: the caller passes one scene's
    shots. Mutates subject dicts in place, returns (shots, notes)."""
    anchors: dict[str, str] = {}
    notes: list[str] = []
    for i, sd in enumerate(shots):
        if not isinstance(sd, dict):
            continue
        action = str(sd.get("action") or "")
        subs = [s for s in (sd.get("subjects") or []) if isinstance(s, dict)]
        names = [n for n in (str(s.get("character") or "").strip() for s in subs) if n]
        for s in subs:
            nm = str(s.get("character") or "").strip()
            if not nm:
                continue
            others = [n for n in names if n != nm]
            if any(pat.search(action) for pat in _anchor_clear_res(nm)):
                anchors.pop(nm.upper(), None)
            for pat in _anchor_res(nm):
                m = pat.search(action)
                if not m:
                    continue
                if _crosses_other_subject(m.group(0), nm, others):
                    continue
                place = next((g for g in m.groups() if g), "").strip()
                if not place or _place_is_bogus(place):
                    continue
                if anchors.get(nm.upper()) != place:
                    anchors[nm.upper()] = place
                    notes.append(f"shot {i + 1}: {nm} anchored at {place}")
                break
        for s in subs:
            nm = str(s.get("character") or "").strip().upper()
            if nm in anchors:
                s["anchor"] = anchors[nm]
    return shots, notes


# A grip already made must not be re-performed: the board restates 抓住 as a
# fresh action in the next shot and the render replays the grab with an
# awkward re-approach. Rewrite the restated grab into a held state (仍...抓着).
_GRIP_VERBS_ZH = "抓住|抓紧|握住|拉住|拽住|捉住|抱住"
_GRIP_RELEASE_RE = re.compile(
    r"松开|放开|甩开|挣脱|松手|放下"
    r"|\b(?:lets?\s+go|releases?|drops?\s+(?:her|his|their)\s+grip)\b",
    re.IGNORECASE)


def _grip_re(target: str) -> re.Pattern:
    nm = re.escape(target)
    return re.compile(
        rf"(紧紧|一把|死死)?({_GRIP_VERBS_ZH})({nm})"
        rf"|\b(grabs?|seizes?|clutch(?:es)?|grips?)\s+({nm})",
        re.IGNORECASE)


def continue_restated_contact(shots: list) -> tuple[list, list[str]]:
    """Track who is gripping whom; a LATER shot restating the same grab is
    rewritten to a continued hold (紧紧抓住 -> 仍紧紧抓着; grabs -> still
    gripping). A visible release ends the contact, after which a fresh grab is
    legitimate again. Mutates shot actions in place, returns (shots, notes)."""
    gripped: set[str] = set()   # target names (upper) currently held
    notes: list[str] = []
    for i, sd in enumerate(shots):
        if not isinstance(sd, dict):
            continue
        action = str(sd.get("action") or "")
        subs = [s for s in (sd.get("subjects") or []) if isinstance(s, dict)]
        names = [str(s.get("character") or "").strip() for s in subs]
        names = [n for n in names if n]
        # (1) rewrite restated grabs on targets already held
        for target in names:
            if target.upper() not in gripped:
                continue
            m = _grip_re(target).search(action)
            if not m:
                continue
            if m.group(2):   # zh form
                adverb = m.group(1) or ""
                verb = m.group(2)
                held = verb[:-1] + "着" if verb.endswith("住") else verb
                new = f"仍{adverb}{held}{m.group(3)}"
            else:            # en form
                new = f"still gripping {m.group(5)}"
            sd["action"] = action = (action[:m.start()] + new
                                     + action[m.end():])
            notes.append(f"shot {i + 1}: restated grab of {target} rewritten "
                         f"to a continued hold")
        # (2) a release ends every contact in this shot
        if gripped and _GRIP_RELEASE_RE.search(action):
            gripped = set()
        # (3) fresh grabs establish contact
        for target in names:
            if target.upper() not in gripped and _grip_re(target).search(action):
                gripped.add(target.upper())
    return shots, notes


_APPROACH_VERBS = (r"(?:walks?|walking|runs?|running|steps?|stepping|moves?|"
                   r"moving|goes|going|comes?|coming|rushes?|rushing|"
                   r"hurries|hurrying)")
_AWAY_RE = re.compile(
    r"\b(?:walks?|steps?|turns?|moves?|backs?|pulls?)\s+(?:\w+\s+){0,2}?away\b"
    r"|\bleaves\b|\bexits?\b|\bstorms?\s+(?:off|out)\b"
    r"|离开|走开|跑开|离去|退出|退下|冲出|跑出|走出|夺门而出|消失在",
    re.IGNORECASE)


def _approach_re(name: str) -> re.Pattern:
    """An approach aimed at THIS partner by name: 'walks over to Leo',
    'runs toward LEO', 'approaches Leo'. Name-gated so 'walks to the
    window' never matches."""
    nm = re.escape(name)
    return re.compile(
        rf"\b(?:{_APPROACH_VERBS}\s+(?:back\s+)?(?:over\s+|up\s+)?"
        rf"(?:to|toward|towards)|approach(?:es|ing)?)\s+(?:the\s+)?({nm})\b",
        re.IGNORECASE)


def _approach_re_zh(name: str) -> re.Pattern:
    """The zh forms of the same name-gated approach: 向NAME走去 / 朝NAME跑来
    (coverb + name + motion verb) and 走向NAME / 靠近NAME (verb + name).
    转向NAME (turns toward) deliberately does NOT match — turning in place is
    legitimate staging, only closing distance is a teleport-reset."""
    nm = re.escape(name)
    return re.compile(
        rf"(?:[向朝往]({nm})(?:身边|这边|那边)?[走跑冲奔扑凑迎靠][了去来近过]*)"
        rf"|(?:(?:走向|走近|跑向|冲向|奔向|扑向|凑近|靠近|迎向|走到)({nm}))")


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
            # the zh drama wrote the same teleport-reset in Chinese (向玛丽走去)
            # and the English pattern never saw it — the render then spawned a
            # SECOND copy of the partner walking in from off-screen
            m = _approach_re_zh(cand).search(text)
            if m:
                who = m.group(1) or m.group(2)
                notes.append(f"shot {i + 1}: approach toward {who} but they "
                             f"are already together - rewritten to stand "
                             f"with them ({where})")
                return text[:m.start()] + f"站在{who}身旁" + text[m.end():]
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
        # are in one framing - the next shot may not re-approach). Sharing it
        # ACROSS a barrier does NOT: a character staged on the far side of a
        # fence (enforce_barrier_depth, which must run FIRST) is seen with the
        # onlookers but not WITH them — approaching them after a crossing is
        # legitimate staging, never a teleport-reset.
        far_u = {n for s, n in zip(subs, names_u)
                 if "far side" in str(s.get("frame_position") or "")}
        for a in range(len(names_u)):
            for b in range(a + 1, len(names_u)):
                if names_u[a] in far_u or names_u[b] in far_u:
                    continue
                together.add(frozenset({names_u[a], names_u[b]}))
        # (3) a visible separation breaks every pair the mover is in
        for s, name_u in zip(subs, names_u):
            texts = f"{s.get('action') or ''} {shot_act}"
            if _AWAY_RE.search(texts):
                together = {p for p in together if name_u not in p}
    return shots, notes


# A physical divider the camera can see through. The seen character stands on
# its FAR side — without depth staging the render put the pet 雪球, seen
# 透过栅栏 (through the fence), shoulder to shoulder with the onlookers.
_BARRIER_ZH = "栅栏|篱笆|围栏|栏杆|铁丝网|围墙|矮墙|窗户|车窗|玻璃|门缝|大门"
_BARRIER_EN = "fence|railing|gate|wall|window|windshield|glass|bars|hedge"
_SEE_ZH = "看到|看见|望见|望着|注视着?|盯着|凝视着?|发现"
# zh: 透过/隔着 + barrier ... see-verb + (seen segment)
_THROUGH_SEE_ZH = re.compile(
    rf"(?:透过|隔着)[^，。！？]*?({_BARRIER_ZH})[^，。！？]*?(?:{_SEE_ZH})([^，。！？]*)")
_SEE_EN = r"(?:sees?|seeing|watches|watching|spots?|spotting|glimpses?|notices?)"
# en, both orders: "sees (X) through the fence" / "through the fence ... sees (X)"
_THROUGH_SEE_EN = re.compile(
    rf"\b{_SEE_EN}\s+([^.!?]*?)\s+through\s+(?:the\s+|a\s+)?({_BARRIER_EN})\b"
    rf"|\bthrough\s+(?:the\s+|a\s+)?({_BARRIER_EN})\b[^.!?]*?\b{_SEE_EN}\s+([^.!?]*)",
    re.IGNORECASE)
_CROSS_RE = re.compile(
    r"\b(?:climbs?|climbing|jumps?|jumping|vaults?|hops?)\s+(?:over|across)\b"
    r"|\b(?:crosses|crossing|enters?|entering)\b"
    r"|\bsteps?\s+(?:inside|into|through)\b|\bopens?\s+the\s+gate\b"
    r"|翻过|爬过|越过|跨过|穿过|钻过|走进|跑进|冲进|进入|推开|打开",
    re.IGNORECASE)


def enforce_barrier_depth(shots: list) -> tuple[list, list[str]]:
    """A character SEEN THROUGH a barrier (安吉琳透过栅栏看到雪球 / 'sees Snowy
    through the fence') is on the barrier's FAR side: stage them deep
    background beyond it, never beside the onlookers — the blocking said only
    'MG right', so the render grouped the pet with the two women. The far-side
    depth THREADS into the scene's later shots (like held props) until a
    crossing (翻过栅栏 / climbs over) dissolves the barrier. Operates on the
    storyboard's shot dicts, mutates subjects in place, returns (shots, notes)."""
    far: dict[str, str] = {}   # subject name upper -> barrier word
    notes: list[str] = []
    for i, sd in enumerate(shots):
        if not isinstance(sd, dict):
            continue
        action = str(sd.get("action") or "")
        subs = [s for s in (sd.get("subjects") or []) if isinstance(s, dict)]
        # a crossing dissolves the divide for the whole scene BEFORE this
        # shot's staging applies (she is through the fence now)
        if far and _CROSS_RE.search(action):
            far = {}
        m = _THROUGH_SEE_ZH.search(action)
        barrier, seen = (m.group(1), m.group(2)) if m else (None, "")
        if not barrier:
            m = _THROUGH_SEE_EN.search(action)
            if m:
                barrier = m.group(2) or m.group(3)
                seen = m.group(1) or m.group(4) or ""
        if barrier and seen.strip():
            for s in subs:
                nm = str(s.get("character") or "").strip()
                if nm and _name_in_text(nm, seen):
                    far[nm.upper()] = barrier
        for s in subs:
            nm = str(s.get("character") or "").strip().upper()
            if nm in far:
                s["frame_position"] = (f"far background, on the far side of "
                                       f"the {far[nm]}, seen through it")
                notes.append(f"shot {i + 1}: {s.get('character')} staged beyond "
                             f"the {far[nm]} (seen through it)")
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


# A name mentioned because the character is GONE is not a visible presence:
# "告诉母亲雪球不见了" names the pet precisely because it is missing, yet the
# named-in-action rule added it to the frame and its identity plate rendered
# the rabbit into the empty-cage shot. Every mention must be absence-marked
# for the character to count as absent; one plain mention means visible.
_ABSENT_AFTER_RE = re.compile(
    r"^[^，。！？.!?]{0,2}?(?:不见了|不见|不在|失踪|丢了|走丢|走失|被送走|"
    # 去哪/哪去了 = "went where" (whereabouts unknown); 哪 keeps it from
    # matching a NAMED destination like 去公园 (went to the park, present)
    r"送走|离开了|没了|死了|不知去向|去哪|去了哪|哪去了|哪儿去了|去向不明)"
    # in a photo, not on screen: "雪球的合影/照片". The 的 is required so a
    # present character looking at a photo (雪球看照片) is NOT matched.
    r"|^的(?:合影|照片|相片|画像|海报|遗像|遗照)"
    r"|^\s*(?:is|was|has|had)\s+(?:gone|missing|lost|nowhere|"
    r"been\s+sold|been\s+given\s+away)"
    r"|^\s*(?:was|got)\s+(?:sold|given\s+away)"
    r"|^\s*(?:disappeared|vanished)"
    # possessive + an empty container is the absent character's, not them:
    # "Snowy's empty hutch", "Snowy's cage, now empty"
    r"|^['’]s\s+(?:\w+[,\s]+){0,3}?empty\b", re.IGNORECASE)
_ABSENT_BEFORE_RE = re.compile(
    r"(?:找不到|寻找|想念|思念|梦见|提起|提到|说起|回忆起?)$"
    r"|(?:missing|look(?:s|ing|ed)?\s+for|search(?:es|ing|ed)?\s+for|"
    r"call(?:s|ing|ed)?\s+(?:out\s+)?for|cr(?:y|ies|ied)\s+(?:out\s+)?for|"
    r"dreams?\s+of|mentions?|sold|gave\s+away)\s*$",
    re.IGNORECASE)


def mention_is_absent(name: str, text: str) -> bool:
    """True when EVERY mention of the name in the text sits in an absence
    context (gone / missing / only talked about); False when any mention is a
    plain, visible one — a reveal line beats an absence line."""
    t = str(text or "")
    nm = str(name or "").strip()
    if not nm or not t:
        return False
    found = False
    for m in re.finditer(re.escape(nm), t, re.IGNORECASE):
        found = True
        if _ABSENT_AFTER_RE.search(t[m.end():]):
            continue
        if _ABSENT_BEFORE_RE.search(t[: m.start()]):
            continue
        return False   # a plain mention: visibly present
    return found


def drop_absent_cast(shots: list,
                     dialogue_lines: list[dict] | None = None) -> tuple[list, list[str]]:
    """Remove cast whose only mentions in the shot's action are absence-marked
    (雪球不见了 / Snowy is gone) — the character is being talked about, not
    shown, and their plate must not ride. The dialogue speaker is never
    dropped (same pairing convention as the other passes). Mutates in place,
    returns (shots, notes)."""
    notes: list[str] = []
    speakers = iter([str(l.get("character") or "").strip()
                     for l in (dialogue_lines or [])])
    for i, sd in enumerate(shots):
        if not isinstance(sd, dict):
            continue
        speaker = ""
        if str(sd.get("dialogue") or "").strip():
            speaker = next(speakers, "")
        action = str(sd.get("action") or "")
        cast = [str(c) for c in (sd.get("characters_in_frame") or [])]
        if not cast or not action:
            continue
        gone = [c for c in cast
                if c.strip().upper() != speaker.strip().upper()
                and mention_is_absent(c, action)]
        if not gone:
            continue
        keep = [c for c in cast if c not in gone]
        sd["characters_in_frame"] = keep
        keep_up = {c.strip().upper() for c in keep}
        sd["subjects"] = [s for s in (sd.get("subjects") or [])
                          if not isinstance(s, dict)
                          or str(s.get("character") or "").strip().upper() in keep_up]
        sd["foreground_characters"] = [
            c for c in (sd.get("foreground_characters") or [])
            if str(c).strip().upper() in keep_up]
        notes.append(f"shot {i + 1}: {', '.join(gone)} only spoken of as "
                     f"absent - removed from the frame")
    return shots, notes


# Which framings can PHYSICALLY show whom: a character staged far beyond a
# barrier (or deep background in a close-up) cannot be visible at that
# framing, yet their listed presence sent their identity plate as a reference
# and the model pasted them in close. Drop them from the frame instead.
_FILTER_FRAMINGS = {"CU", "ECU", "MCU", "INSERT"}


def _far_staged(subject: dict) -> bool:
    pos = str((subject or {}).get("frame_position") or "").lower()
    return "far background" in pos or "far side" in pos


def filter_frame_by_framing(shots: list,
                            dialogue_lines: list[dict] | None = None) -> tuple[list, list[str]]:
    """Drop cast a shot's framing cannot physically show: far-staged subjects
    from CU/ECU/MCU (plain BG additionally from CU/ECU), and INSERT shots
    narrow to cast named in their own action. The dialogue speaker (paired in
    speaking order, the widen_tight_two_shots convention), the shot's
    `subject`, and foreground occluders are never dropped. Subjects and
    foreground_characters stay consistent with the new cast. Mutates in
    place, returns (shots, notes)."""
    notes: list[str] = []
    speakers = iter([str(l.get("character") or "").strip()
                     for l in (dialogue_lines or [])])
    for i, sd in enumerate(shots):
        if not isinstance(sd, dict):
            continue
        speaker = ""
        if str(sd.get("dialogue") or "").strip():
            speaker = next(speakers, "")
        stype = str(sd.get("shot_type") or "").upper()
        cast = [str(c) for c in (sd.get("characters_in_frame") or [])]
        if stype not in _FILTER_FRAMINGS or not cast:
            continue
        keep = {speaker.strip().upper()} if speaker.strip() else set()
        subj_name = str(sd.get("subject") or "").strip()
        if subj_name:
            keep.add(subj_name.upper())
        keep |= {str(c).strip().upper()
                 for c in (sd.get("foreground_characters") or [])}
        by_name = {str(s.get("character") or "").strip().upper(): s
                   for s in (sd.get("subjects") or []) if isinstance(s, dict)}

        def visible(name: str) -> bool:
            up = name.strip().upper()
            if up in keep:
                return True
            if stype == "INSERT":
                return _name_in_text(name, str(sd.get("action") or ""))
            s = by_name.get(up) or {}
            if _far_staged(s):
                return False
            if stype in ("CU", "ECU"):
                return str(s.get("frame_position") or "").strip().upper() != "BG"
            return True

        new = [c for c in cast if visible(c)]
        if new == cast:
            continue
        dropped = [c for c in cast if c not in new]
        sd["characters_in_frame"] = new
        new_up = {c.strip().upper() for c in new}
        sd["subjects"] = [s for s in (sd.get("subjects") or [])
                          if not isinstance(s, dict)
                          or str(s.get("character") or "").strip().upper() in new_up]
        sd["foreground_characters"] = [
            c for c in (sd.get("foreground_characters") or [])
            if str(c).strip().upper() in new_up]
        notes.append(f"shot {i + 1}: {stype} cannot show "
                     f"{', '.join(dropped)} - dropped from the frame")
    return shots, notes
