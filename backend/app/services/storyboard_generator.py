import json
from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.config import get_settings
from app.director.types import ShotPlan


def plan_shot_budget(num_scenes: int, target_length: int) -> tuple[int, int]:
    """Given the scene count and target length (seconds), return how many shots
    per scene and how long each shot should be so the total ≈ target_length."""
    num_scenes = max(1, num_scenes)
    total_budget = max(num_scenes, round(target_length / 5))  # ~5s per shot
    shots_per_scene = max(1, round(total_budget / num_scenes))
    total_shots = shots_per_scene * num_scenes
    shot_seconds = max(2, round(target_length / total_shots))
    return shots_per_scene, shot_seconds


# A clip's length follows what is spoken in it, so a long line isn't crammed into
# 5s. Sized to the tier that fits the line. Capped at 10s: Wan handles 15s but
# HappyHorse's ceiling isn't documented, and long single takes drift the face
# more — raise the top tier once the models are confirmed to accept it.
DURATION_TIERS = (5, 10)
_WORDS_PER_SEC = 2.6  # natural drama delivery pace


def fit_duration_to_dialogue(text: str | None, tiers: tuple = DURATION_TIERS) -> int:
    """Smallest clip tier that comfortably holds the spoken line; the base tier
    for an action beat with no dialogue."""
    words = len((text or "").split())
    if words == 0:
        return tiers[0]
    needed = words / _WORDS_PER_SEC + 0.8  # small pad for breath/pauses
    for t in tiers:
        if needed <= t:
            return t
    return tiers[-1]


def _default_subjects(names) -> list[dict]:
    """Deterministic blocking when the Stager LLM omits `subjects`, so the
    interactive camera plan always has geometry to draw. A two-hander faces each
    other across the frame; a solo subject faces camera; extras face center. The
    stage map then keeps screen sides consistent across the scene."""
    names = [str(n).strip() for n in (names or []) if str(n).strip()]
    if not names:
        return []
    if len(names) == 1:
        return [{"character": names[0], "frame_position": "MG", "screen_side": "center",
                 "facing": "camera", "eyeline": "camera", "posture": "standing"}]
    sides = ["left", "right", "center"]
    facings = {"left": "right", "right": "left", "center": "camera"}
    out = []
    for i, n in enumerate(names):
        side = sides[i % len(sides)]
        out.append({"character": n, "frame_position": "MG", "screen_side": side,
                    "facing": facings[side], "eyeline": "toward the other character",
                    "posture": "standing"})
    return out


def _ensure_speakers_in_frame(cast, speakers) -> list:
    """A talking shot MUST show its speaker: native-talk animates the on-screen
    mouth, so a line assigned to an empty frame renders nobody 'speaking'. Force
    each covered line's speaker into the cast (deduped, order preserved)."""
    out = [str(c) for c in (cast or []) if str(c).strip()]
    for spk in speakers or []:
        spk = str(spk or "").strip()
        if spk and not any(c.strip().upper() == spk.upper() for c in out):
            out.append(spk)
    return out


def scene_opens_on_scenery(shots: list[dict]) -> bool:
    """True when the scene already has a people-free silent shot — empty
    characters_in_frame AND no dialogue — the shot the router sends to Wan. When
    absent, an establishing shot can be prepended to guarantee a Wan visual."""
    for s in (shots or []):
        if (not (s.get("characters_in_frame") or [])
                and not str(s.get("dialogue") or "").strip()):
            return True
    return False


def make_establishing_shot(location, lighting, colour_mood) -> dict:
    """A people-free establishing wide: empty cast + no dialogue, so the router
    sends it to Wan — its real strength is cinematic scenery with no identity to
    lock. Placed as a scene's FIRST shot (the anchor, no previous frame), it is
    a silent faceless anchor, which routes to Wan.

    The action describes ONLY the environment — NEVER the scene's character
    action. The scene description is all about the cast (who cries, who enters);
    pasting it into a 'people-free' shot both contradicts itself and makes the
    model render those people. The set dresser enriches the room at craft time."""
    where = str(location or "the location").strip()
    action = (f"Establishing wide of {where}. No people in frame - only the "
              "empty environment, its light and atmosphere.")
    return {
        "shot_number": 1,
        "shot_type": "EWS",
        "camera_movement": "DOLLY_IN",
        "characters_in_frame": [],
        "subject": None,
        "foreground_characters": [],
        "subjects": [],
        "reverse_angle": False,
        "action": action,
        "dialogue": None,
        "lighting": lighting,
        "colour_mood": colour_mood,
        "emotional_beat": "the world before anyone arrives",
        "estimated_duration_seconds": 3,
        "notes": "people-free establishing shot (Wan visual)",
    }


def plan_hold_budget(target_length: int | None) -> int:
    """Drama-level silent-hold budget: about one held beat per 45s of target
    runtime, floor 1 (even a short piece gets one breath), cap 2. Budgeted per
    drama, not per scene — 2-per-scene piled three identical held beats onto a
    30-second two-scene drama and read as repetition."""
    return min(2, max(1, round((target_length or 0) / 45)))


# Distinct silent looks so multiple held beats never read as the same repeating
# shot. Every look continues the moment (no new gesture, no reposition), so the
# frame still matches the preceding shot for a Wan continuation. The tag lets
# the picker match the tone of the line just spoken.
_HELD_BEAT_LOOKS = (
    ("They hold still, the last words settling between them, neither ready to speak.",
     "the weight of what was just said", "emotion"),
    ("Neither of them moves. The silence stretches taut, eyes locked, nothing given away.",
     "unspoken tension", "tension"),
    ("A held pause. They watch each other, waiting to see what comes next.",
     "waiting for the reply", "anticipation"),
    ("The moment rests unspoken. Stillness, a slow breath, thoughts turning behind their eyes.",
     "a quiet beat of reflection", "reflection"),
)


def _held_look_index(prev: dict, last_variant: int) -> int:
    """Pick the held-beat look from the tone of the line it holds after — a
    question hangs in anticipation, an exclamation in tension — falling back to
    rotation, and never reusing the previous hold's look."""
    line = str(prev.get("dialogue") or "").strip()
    want = ("anticipation" if line.endswith("?")
            else "tension" if line.endswith("!") else None)
    if want is not None:
        idx = next(i for i, l in enumerate(_HELD_BEAT_LOOKS) if l[2] == want)
        if idx != last_variant:
            return idx
    return (last_variant + 1) % len(_HELD_BEAT_LOOKS)


def _held_beat(prev: dict, variant: int = 0) -> dict:
    """A silent held beat that copies the PRECEDING shot's framing, cast and
    blocking with NO dialogue, so it routes to Wan (a silent same-angle
    continuation of established faces — two people holding the moment between
    lines). Same shot_type as prev -> not a reangle; same cast -> not a
    newcomer; silent -> continue_hold -> Wan. `variant` picks the look from
    _HELD_BEAT_LOOKS. Blocking keeps each subject's position/facing/eyeline but
    drops the per-subject `action`: that gesture already finished in the
    previous shot, and restating it makes the hold replay it."""
    cast = list(prev.get("characters_in_frame") or [])
    action, beat, _tag = _HELD_BEAT_LOOKS[variant % len(_HELD_BEAT_LOOKS)]
    subjects = [{k: v for k, v in s.items() if k != "action"}
                for s in (prev.get("subjects") or []) if isinstance(s, dict)]
    return {
        "shot_number": 0,        # caller renumbers
        "shot_type": prev.get("shot_type") or "MS",
        "camera_movement": "STATIC",
        "characters_in_frame": cast,
        "subject": prev.get("subject"),
        "foreground_characters": list(prev.get("foreground_characters") or []),
        "subjects": subjects,
        "reverse_angle": False,
        "action": action,
        "dialogue": None,
        "lighting": prev.get("lighting"),
        "colour_mood": prev.get("colour_mood"),
        "emotional_beat": beat,
        "estimated_duration_seconds": 3,
        "notes": "silent held beat (Wan continuation)",
    }


def insert_silent_holds(shots: list[dict], max_holds: int = 2,
                        last_variant: int = -1) -> tuple[list[dict], int]:
    """Weave silent held beats between consecutive DIALOGUE shots that share a
    stable 2+ person cast: the held beat keeps the preceding shot's framing and
    cast with no dialogue, so it routes to Wan. Bounded to max_holds (the
    caller passes the DRAMA-level remainder) and spaced (never two in a row).
    Each hold takes a different look; `last_variant` threads the previous
    hold's look in (and back out through the return) so wording never repeats,
    even across scenes. Returns (new list NOT renumbered, last look used)."""
    if max_holds <= 0 or len(shots) < 2:
        return list(shots), last_variant
    out: list[dict] = []
    holds = 0
    i, n = 0, len(shots)
    while i < n:
        s = shots[i]
        out.append(s)
        nxt = shots[i + 1] if i + 1 < n else None
        cast_a = [str(c) for c in (s.get("characters_in_frame") or [])]
        if (holds < max_holds and nxt is not None and len(cast_a) >= 2
                and str(s.get("dialogue") or "").strip()
                and str(nxt.get("dialogue") or "").strip()
                and set(cast_a) <= {str(c) for c in (nxt.get("characters_in_frame") or [])}):
            last_variant = _held_look_index(s, last_variant)
            out.append(_held_beat(s, last_variant))
            out.append(nxt)           # keep the next line, and space the holds out
            holds += 1
            i += 2
            continue
        i += 1
    return out, last_variant


# Distinct looks so multiple cutaways (and the establishing wide) never render
# as the same repeating shot: different framing, camera and phrasing. Each is
# environment-only, never the scene's character action. Framings are WIDE only
# (EWS/WS/LS): a scenery shot has no body to frame, so a person framing like MS
# or CU on an empty environment reads as a broken, awkward shot.
_ATMOSPHERE_LOOKS = [
    ("A still, unpeopled wide of {where} - its light, texture and empty space, "
     "not a soul in frame.", "WS", "STATIC"),
    ("A slow drift across the empty {where} - atmosphere and light only, no "
     "people present.", "LS", "PAN_RIGHT"),
    ("A high, sweeping view of {where} holding its silence - no one in frame.",
     "EWS", "DRONE"),
]


def make_atmosphere_shot(location, lighting, colour_mood, variant: int = 0) -> dict:
    """A faceless atmosphere cutaway (empty cast, no dialogue) — a breath of the
    place mid-scene. Routes to Wan (no identity to lock, even on an angle cut).
    `variant` picks a distinct framing/phrasing so it never repeats the
    establishing wide or another cutaway. Environment only, never the cast."""
    where = str(location or "the location").strip()
    text, stype, cam = _ATMOSPHERE_LOOKS[variant % len(_ATMOSPHERE_LOOKS)]
    return {
        "shot_number": 0,
        "shot_type": stype,
        "camera_movement": cam,
        "characters_in_frame": [],
        "subject": None,
        "foreground_characters": [],
        "subjects": [],
        "reverse_angle": False,
        "action": text.format(where=where),
        "dialogue": None,
        "lighting": lighting,
        "colour_mood": colour_mood,
        "emotional_beat": "a breath of the place",
        "estimated_duration_seconds": 3,
        "notes": "atmosphere cutaway (Wan visual)",
    }


def insert_atmosphere(shots: list[dict], count: int, location,
                      lighting, colour_mood) -> list[dict]:
    """Insert up to `count` faceless atmosphere cutaways, spaced across the
    scene, each just before a DIALOGUE shot AND at least 2 shots from any
    existing people-free shot (the establishing wide or another cutaway) — so
    two scenery shots never bunch up and look repeating. The shot after a cutaway
    must be a talking shot (HappyHorse regardless), never a silent held beat,
    whose Wan routing depends on continuing DIRECTLY from its dialogue anchor.
    Each cutaway gets a distinct look. Returns a new list; NOT renumbered."""
    out = list(shots)
    if count <= 0 or not out:
        return out
    empty_idx = [i for i, s in enumerate(out) if not (s.get("characters_in_frame") or [])]

    def _pausable(prev: dict) -> bool:
        # conversation continuity: a cutaway may only follow a COMPLETED
        # statement — never split a question from its answer or a trailing,
        # unfinished line from its continuation
        line = str(prev.get("dialogue") or "").rstrip()
        return not line.endswith(("?", "...", "…"))

    slots = [i for i, s in enumerate(out)
             if i >= 1 and str(s.get("dialogue") or "").strip()
             and _pausable(out[i - 1])
             and all(abs(i - e) > 2 for e in empty_idx)]
    if not slots:
        return out   # nowhere safe -> skip rather than bunch scenery together
    k = min(count, len(slots))
    # spread the chosen slots EVENLY across what's available (not the first k),
    # so multiple cutaways don't cluster and end up adjacent after insertion
    if k == 1:
        chosen = [slots[len(slots) // 2]]
    else:
        chosen = sorted({slots[round(j * (len(slots) - 1) / (k - 1))] for j in range(k)})
    # insert from the back so earlier indices stay valid as the list grows;
    # variant index gives each a distinct framing/phrasing
    for n, at in enumerate(reversed(chosen)):
        out.insert(at, make_atmosphere_shot(location, lighting, colour_mood, variant=n))
    return out


# A person framing implies a body in the frame; on a scenery shot with no cast
# it renders as an awkward, subjectless shot ("a medium shot of nothing").
_PERSON_FRAMINGS = {"MCU", "MS", "FS", "OTS", "POV"}
_DETAIL_FRAMINGS = {"CU", "ECU"}


def widen_faceless_framings(shots: list[dict]) -> list[dict]:
    """Any shot with NO characters in frame must not wear a person framing.
    A faceless MCU/MS/FS/OTS/POV is a body framing with no body — snap it to LS
    so an empty-cast Wan shot doesn't render as a broken shot of nothing. A
    faceless CU/ECU is different: the Director meant a DETAIL (a trembling
    hand, an object) — widening it to LS destroys the shot, so it becomes
    INSERT instead. EWS/WS/LS (already wide) and INSERT are left alone.
    Must run AFTER the cast is final (the reconciler can empty a shot's cast).
    Mutates in place, returns it."""
    for s in (shots or []):
        if not (s.get("characters_in_frame") or []):
            stype = str(s.get("shot_type") or "").upper()
            if stype in _PERSON_FRAMINGS:
                s["shot_type"] = "LS"
            elif stype in _DETAIL_FRAMINGS:
                s["shot_type"] = "INSERT"
    return shots


def board_over_target(boarded_seconds: int, target_length: int | None,
                      tolerance: float = 0.3) -> bool:
    """True when the boarded runtime overshoots the requested target by more
    than the tolerance — the signal to warn BEFORE render money is spent (a
    30s ask that boards 97s). No target, no warning."""
    if not target_length:
        return False
    return boarded_seconds > round(target_length * (1 + tolerance))


class StoryboardGenerator:
    # Never balloon a single scene past this many shots, even if it is very
    # dialogue-heavy — keeps cost and length sane.
    _HARD_CAP = 12

    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("storyboard_generate.txt")

    async def generate_for_scene(
        self,
        scene_json: dict,
        characters_in_scene: list[dict],
        style_bible: dict | None = None,
        max_shots: int = 4,
        shot_seconds: int = 5,
    ) -> list[dict]:
        # Grow the budget so no scripted line is dropped: the scene's dialogue is
        # covered in order, roughly one line (or a short exchange) per shot.
        lines = scene_json.get("dialogue") or []
        cap = min(max(max_shots, len(lines)), self._HARD_CAP)

        user_content = (
            f"Scene details:\n{json.dumps(scene_json, ensure_ascii=False)}\n\n"
            f"Characters involved:\n{json.dumps(characters_in_scene, ensure_ascii=False)}\n\n"
            f"Director's style bible:\n{json.dumps(style_bible or {}, ensure_ascii=False)}\n\n"
            f"This scene has {len(lines)} dialogue line(s). Produce at most {cap} "
            f"shot(s), plus ONE extra shot for each react-then-reveal pair if the "
            f"scene contains an entrance or discovery beat. Preserve EVERY dialogue "
            f"line verbatim and in order; do not invent beats or endings. Clip "
            f"length is set automatically to fit each spoken line, so give each "
            f"shot the dialogue it should carry."
        )
        if getattr(get_settings(), "cinematic_prompt", False):
            user_content += (
                "\n\nCAMERA (choose a `camera_movement` that SERVES the beat; do NOT default to STATIC):\n"
                "- tension / intimacy / a dawning realization -> DOLLY_IN (push in)\n"
                "- isolation / loss / scale -> DOLLY_OUT (pull out)\n"
                "- follow a subject or reveal -> PAN_LEFT/PAN_RIGHT/TILT_UP/TILT_DOWN\n"
                "- a deliberate, held standoff -> STATIC (reserved, never the default)\n"
                "Use HANDHELD/DRONE sparingly. One smooth move per shot.\n")
        messages = [
            {"role": "system", "content": self.prompt_template},
            {"role": "user", "content": user_content},
        ]
        result = await self.qwen.chat_json(messages=messages, temperature=0.4, task="storyboard")
        # JSON mode may wrap the array in an object — unwrap it
        shots = QwenClient.as_list(result)

        shots = shots[:cap]
        # Clip length follows the spoken line, not a uniform target — a long line
        # gets a longer clip so the video can actually cover it.
        for s in shots:
            if isinstance(s, dict):
                s["estimated_duration_seconds"] = fit_duration_to_dialogue(
                    s.get("dialogue"))
        return shots

    async def stage_plan(self, scene_json: dict, characters_in_scene: list[dict],
                         plan: ShotPlan, style_bible: dict | None = None) -> list[dict]:
        """Stager: fill blocking/action/verbatim-dialogue INSIDE a fixed director
        plan. The plan's cinematic choices (size/camera/lens/composition/duration)
        are authoritative and forced after staging. Raises on LLM failure so the
        caller can fall back to generate_for_scene."""
        from app.services.prompt_loader import load_prompt
        lines = scene_json.get("dialogue") or []
        plan_rows = [{
            "shot_number": i + 1, "purpose": s.purpose, "shot_size": s.shot_size,
            "camera_movement": s.camera_movement, "lens": s.lens, "composition": s.composition,
            "covers_lines": s.covers_lines, "action_beat": s.action_beat,
            "blocking_delta": s.blocking_delta,
        } for i, s in enumerate(plan.shots)]
        user_content = (
            f"Scene details:\n{json.dumps(scene_json, ensure_ascii=False)}\n\n"
            f"Characters involved:\n{json.dumps(characters_in_scene, ensure_ascii=False)}\n\n"
            f"Director's style bible:\n{json.dumps(style_bible or {}, ensure_ascii=False)}\n\n"
            f"THE SHOT PLAN (stage each in order; do not change size/camera/lens/composition):\n"
            f"{json.dumps(plan_rows, ensure_ascii=False)}\n\n"
            f"The scene's dialogue lines by index:\n"
            f"{json.dumps({i: l.get('line') for i, l in enumerate(lines)}, ensure_ascii=False)}"
        )
        stage_prompt = load_prompt("storyboard_stage.txt")
        result = await self.qwen.chat_json(
            messages=[{"role": "system", "content": stage_prompt},
                      {"role": "user", "content": user_content}],
            temperature=0.4, task="storyboard_stage")
        staged = QwenClient.as_list(result)
        out: list[dict] = []
        for i, planned in enumerate(plan.shots):
            sd = staged[i] if i < len(staged) and isinstance(staged[i], dict) else {}
            # the plan is authoritative for cinematic intent — force it, don't trust the LLM echo
            sd["shot_number"] = i + 1
            sd["shot_type"] = planned.shot_size
            sd["camera_movement"] = planned.camera_movement
            sd["director_json"] = {
                "purpose": planned.purpose, "lens": planned.lens,
                "composition": planned.composition,
                "light_quality": planned.light_quality,
                "stylization": planned.stylization,
                "special_effect": planned.special_effect,
                "intended_duration": planned.intended_duration,
                "transition_in": planned.transition_in,
                "blocking_delta": planned.blocking_delta,
            }
            # verbatim dialogue for the covered lines, in order (coverage invariant)
            covered = [str(lines[j].get("line")) for j in planned.covers_lines
                       if 0 <= j < len(lines) and lines[j].get("line")]
            sd["dialogue"] = " ".join(covered) if covered else None
            # a dialogue floor so a spoken line is never cut off; else the plan's rhythm
            from app.services.storyboard_generator import fit_duration_to_dialogue
            sd["estimated_duration_seconds"] = (fit_duration_to_dialogue(sd["dialogue"])
                                                if covered else round(planned.intended_duration))
            # a talking shot must show its speaker, or native-talk renders an empty
            # frame "speaking": force each covered line's speaker into the cast
            line_speakers = [lines[j].get("character") for j in planned.covers_lines
                             if 0 <= j < len(lines)]
            sd["characters_in_frame"] = _ensure_speakers_in_frame(
                sd.get("characters_in_frame"), line_speakers)
            # the interactive camera plan draws from blocking `subjects`; the Stager
            # LLM often omits them, so backfill a deterministic default from who is
            # in frame (the stage map then enforces the 180-degree rule across shots)
            from app.services.stage_map import normalize_subjects
            if not normalize_subjects(sd.get("subjects")):
                names = sd.get("characters_in_frame") or [c.get("name") for c in characters_in_scene]
                sd["subjects"] = _default_subjects(names)
            out.append(sd)
        return out
