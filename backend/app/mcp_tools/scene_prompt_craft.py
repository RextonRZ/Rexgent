import json
import re
from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.services.guardrails import PromptSanitizer, strip_character_names
from app.config import get_settings

# Identity-pin vocabularies (rule 22): what a character wears on the face and
# hair must be stated in EVERY shot's prompt, or the render coin-flips it.
# EN "hair" plus Chinese hair terms — a 中文 character's description never says
# "hair" (it says 长发/黑发/卷发/马尾...), so without these the hairstyle went
# completely unpinned on Chinese dramas and drifted every shot.
_HAIR_RE = re.compile(
    r"\bhair\b|头发|頭髮|发型|髮型|长发|長髮|短发|短髮|卷发|捲髮|直发|直髮|"
    r"披肩发|马尾|馬尾|辫子|辮子|刘海|瀏海|盘发|盤髮|黑发|黑髮|金发|金髮|"
    r"棕发|棕髮|波浪|发丝|髮絲|寸头|平头", re.I)
_EYEWEAR_RE = re.compile(
    r"glasses|spectacles|eyewear|sunglasses|眼镜|墨镜|太阳镜", re.I)
_ACCESSORY_RE = re.compile(
    r"headband|hairpin|hair\s*clip|hair\s*bow|bow\s+headband|ribbon|tiara|"
    r"hair accessor|发箍|发带|发夹|发绳|蝴蝶结|头饰|丝带|头绳", re.I)
_FACIAL_HAIR_RE = re.compile(
    r"clean-shaven|beard|moustache|mustache|stubble|goatee|facial hair|"
    r"胡子|胡须|络腮胡|山羊胡|八字胡|干净的下巴", re.I)
# Headwear (rule 22): a cap/beanie/hat is kept OUT of the identity fragment by
# design (it occludes the face plate) and is unknown to _pin_segments, so it
# rode on the crafter LLM's whim and flickered shot to shot (the Lucas cap bug).
_HEADWEAR_RE = re.compile(
    r"beanie|knit\s*cap|\bcap\b|\bhat\b|\bhood\b|toque|headwear|headscarf|"
    r"turban|帽子|棒球帽|毛线帽|鸭舌帽|头巾|兜帽", re.I)

_ACTION_CAMERA_RE = re.compile(r"\b(?:the\s+)?camera\b", re.I)
# An EXIT action ("runs away", "runs out of the frame", "disappearing into
# the distance") means the character recedes from camera to the last frame.
# Continuation models love turning the runner to the lens at the clip tail -
# and the stager's `facing` is too drifty (a literal 'right') to rely on.
_EXIT_RE = re.compile(
    r"\b(?:runs?|running|walks?|walking|dash(?:es)?|dashing|storms?|storming|"
    r"hurries|hurrying|rush(?:es)?|rushing|flees?|fleeing|sprints?|sprinting)\s+"
    r"(?:away|off|out)\b"
    r"|\bdisappear(?:s|ing)?\s+into\b"
    r"|挣脱|离开|走开|跑开|走出|跑出|冲出|转身离|头也不回|夺门而出", re.I)


def exiting_characters(action: str | None, names: list) -> list[str]:
    """Which in-frame characters EXIT during this shot. A character exits when
    their name precedes an exit phrase with no OTHER cast name between them
    ('Claire stands as Angeline runs out' exits Angeline, not Claire)."""
    text = str(action or "")
    if not text or not names:
        return []
    out = []
    for name in names:
        nm = str(name)
        # a nickname pair (Sam/Samantha, 玛丽/小玛丽) must never credit the
        # LONGER name's exit to the shorter one: mask every other cast name
        # that contains this one before scanning (\b can't do this for CJK)
        masked = text
        for other in names:
            o = str(other)
            if o != nm and nm in o:
                masked = masked.replace(o, "\x00" * len(o))
        others = "|".join(re.escape(str(n)) for n in names if n != name)
        gap = (rf"(?:(?!(?:{others}))[^.!?。！？；])*?" if others
               else r"[^.!?。！？；]*?")
        pat = re.compile(
            rf"{re.escape(nm)}{gap}(?:{_EXIT_RE.pattern})", re.I)
        if pat.search(masked):
            out.append(nm)
    return out
_AGE_RE = re.compile(r"\b(\d{1,2})\s*[- ]\s*year[- ]old\b", re.I)
# zh fragments write ages as 10岁 or 三十八岁 — the English-only pattern never
# matched, so the height pin silently skipped zh casts (the girl rendered
# taller than her mother)
_AGE_DIGIT_ZH_RE = re.compile(r"(\d{1,2})\s*岁")
_AGE_NUMERAL_ZH_RE = re.compile(r"([一二两三四五六七八九十]{1,3})岁")
_ZH_DIGITS = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9}


def _zh_numeral(s: str) -> int | None:
    """三十八 -> 38, 十 -> 10, 十二 -> 12; None for anything else."""
    if not s:
        return None
    if "十" in s:
        left, _, right = s.partition("十")
        tens = _ZH_DIGITS.get(left, 1) if left else 1
        ones = _ZH_DIGITS.get(right, 0) if right else 0
        if (left and left not in _ZH_DIGITS) or (right and right not in _ZH_DIGITS):
            return None
        return tens * 10 + ones
    return _ZH_DIGITS.get(s)


def _ages_in(text: str) -> list[int]:
    """Every age stated in a fragment, English or Chinese forms."""
    ages = [int(m) for m in _AGE_RE.findall(text)]
    ages += [int(m) for m in _AGE_DIGIT_ZH_RE.findall(text)]
    for m in _AGE_NUMERAL_ZH_RE.findall(text):
        n = _zh_numeral(m)
        if n is not None:
            ages.append(n)
    return ages


def child_scale_clause(character_visuals: dict) -> str:
    """A child sharing the frame with a much older character kept rendering
    at adult height (an 8-year-old suddenly 'so tall'). When the fragments
    carry ages and the gap is real, pin the size relation explicitly."""
    ages = []
    for v in (character_visuals or {}).values():
        frag = v.get("video_prompt_fragment") if isinstance(v, dict) else v
        ages.extend(_ages_in(str(frag or "")))
    if len(ages) < 2:
        return ""
    youngest, oldest = min(ages), max(ages)
    if youngest <= 12 and oldest >= youngest + 5:
        return (f" The {youngest}-year-old is a small child with a true "
                f"child's height and body proportions - clearly much shorter "
                f"than the older characters, the same size relation in every "
                f"frame.")
    return ""


# zh species words mapped to the English noun the scale clause names (the
# clause itself stays English for the video model); en species pass through
_SPECIES_EN = {
    "兔": "rabbit", "兔子": "rabbit", "猫": "cat", "狗": "dog", "鸟": "bird",
    "鼠": "mouse", "仓鼠": "hamster", "鸭": "duck", "鹅": "goose",
    "鸡": "chicken", "龟": "turtle", "蛙": "frog", "宠物": "pet",
    "犬": "dog", "博美": "dog", "柯基": "dog", "哈士奇": "dog", "金毛": "dog",
    "泰迪": "dog", "吉娃娃": "dog", "柴犬": "dog", "贵宾": "dog",
    "拉布拉多": "dog", "萨摩耶": "dog", "边牧": "dog",
}


def creature_scale_clause(character_visuals: dict) -> str:
    """An animal sharing the frame with people kept inflating (the pet rabbit
    rendered half the girl's height) - nothing pinned its real-world size the
    way child_scale_clause pins children. For each creature in a peopled
    frame, state its species at true scale. Empty when the frame has no
    creature or no human to scale against."""
    from app.services.character_traits import species_of
    species: list[str] = []
    humans = 0
    for v in (character_visuals or {}).values():
        frag = v.get("video_prompt_fragment") if isinstance(v, dict) else v
        sp = species_of(str(frag or ""))
        if sp:
            species.append(_SPECIES_EN.get(sp, sp))
        else:
            humans += 1
    if not species or not humans:
        return ""
    bits = []
    for sp in dict.fromkeys(species):
        bits.append(f" The {sp} is a real {sp} at true real-world size - "
                    f"small beside the people, never enlarged, the same size "
                    f"relation in every frame.")
    return "".join(bits)


def headwear_pin(fragment: str | None, outfit: str | None) -> str:
    """Headwear (a cap, beanie or hat) is kept OUT of the identity fragment by
    design and is unknown to _pin_segments, so it rode on the crafter LLM's
    whim and flickered shot to shot (the Lucas cap bug). Return the wardrobe
    segment that names the headwear - from the outfit, where it actually
    lives, or the fragment as a fallback - so the identity lock can re-state
    it in every shot. Empty when the character wears none."""
    for source in (outfit, fragment):
        for seg in re.split(r"[,;.]", str(source or "")):
            seg = seg.strip()
            if seg and _HEADWEAR_RE.search(seg):
                return seg
    return ""


_HAIR_DEFER = ("hair length, cut, parting and color exactly as shown in "
               "their reference image, never a different length")


def _defer_hair_to_image(cdesc):
    """THE PLATE IS THE BOSS for hair. The appearance LLM invents a textual
    length ("chin-length") that can contradict the rendered plate (long) — and
    the video model obeys the TEXT, so the drama's hair never matches the
    plate the user approved. When the character's plate rides the shot as a
    reference image, replace every textual hair-length/style segment with a
    defer-to-image clause; accessory and facial-hair pins stay (those flicker
    without text). Returns a copy, never mutates the bible."""
    def _swap(text: str) -> str:
        segs = [t.strip() for t in re.split(r"[,;.，、。；]", str(text or ""))
                if t.strip()]
        kept, swapped = [], False
        for t in segs:
            if (_HAIR_RE.search(t) and not _ACCESSORY_RE.search(t)
                    and not _FACIAL_HAIR_RE.search(t)):
                if not swapped:
                    kept.append(_HAIR_DEFER)
                    swapped = True
                continue
            kept.append(t)
        return ", ".join(kept)
    if isinstance(cdesc, dict):
        out = dict(cdesc)
        for key in ("video_prompt_fragment", "visual_description",
                    "physical_description", "full_description"):
            if out.get(key):
                out[key] = _swap(out[key])
        return out
    return _swap(cdesc)


def _pin_segments(text: str) -> list[str]:
    segs = [t.strip() for t in re.split(r"[,;.，、。；]", text) if t.strip()]
    pins: list[str] = []
    # every hair segment (length, colour, style, parting), not just the first —
    # matched in EN and Chinese so 长发/中分/波浪 all get pinned, capped so the
    # pin can't run away
    hairs = [t for t in segs if _HAIR_RE.search(t) and not _ACCESSORY_RE.search(t)]
    if hairs:
        joiner = "，" if re.search(r"[一-鿿]", " ".join(hairs)) else ", "
        pins.append(joiner.join(hairs[:3]))
    eye = next((t for t in segs if _EYEWEAR_RE.search(t)), None)
    pins.append(eye or "no eyewear")
    face = next((t for t in segs if _FACIAL_HAIR_RE.search(t)), None)
    if face:
        pins.append(face)
    acc = next((t for t in segs if _ACCESSORY_RE.search(t)), None)
    pins.append(acc or "no hair accessories")
    return pins


_ABSORBED_EYELINE = ("on what they are doing - absorbed in the action, "
                     "never toward the lens")
_LISTENER_EYELINE = ("just beside the camera, at the off-screen person they "
                     "are speaking to - the gaze rests close past the lens, "
                     "never directly into it")
_OFFSCREEN_RE = re.compile(r"off[- ]?screen", re.I)
_EYELINE_TARGET_RE = re.compile(r"^(?:at|toward|towards)\s+(.+)$", re.I)


def solo_eyeline(raw: str | None) -> str:
    """A solo subject's vague eyeline resolves to TASK ABSORPTION, not just
    off-lens: 'off-camera' alone still rendered a Dora-the-Explorer host
    presenting to the audience while supposedly searching. A specific eyeline
    the board wrote ('at the empty hutch') survives untouched."""
    t = str(raw or "").strip().lower()
    vague = {"camera", "at camera", "the camera", "at the camera", "off-camera",
             "just off-camera", "off camera", "toward the other character", ""}
    if t in vague or t.startswith("just off-camera"):
        return _ABSORBED_EYELINE
    return str(raw).strip()


def resolve_solo_eyeline(raw: str | None, frame_names: list) -> tuple[str, str]:
    """(text, mode) for a solo subject's eyeline. Three modes:
    - "listener": the eyeline names a PERSON who is not in this frame (the
      clean single of a conversation - the other character stands off-screen
      at the camera position). The gaze rests just beside the lens, and the
      off-frame name never enters the prompt (it would render that person).
    - "authored": a specific non-person eyeline the board wrote ('at the
      empty hutch') survives untouched.
    - "absorbed": vague eyelines become task absorption (the Dora fix)."""
    t = str(raw or "").strip()
    in_frame_upper = {str(n).strip().upper() for n in (frame_names or [])}
    if _OFFSCREEN_RE.search(t):
        return _LISTENER_EYELINE, "listener"
    m = _EYELINE_TARGET_RE.match(t)
    if m:
        target = m.group(1).strip().rstrip(".")
        first = target.split()[0] if target.split() else ""
        looks_like_object = first.lower() in (
            "the", "a", "an", "his", "her", "their", "its", "what")
        if not looks_like_object and first[:1].isupper():
            if target.upper() in in_frame_upper:
                # self-reference noise ("Angeline looks at Angeline")
                return _ABSORBED_EYELINE, "absorbed"
            return _LISTENER_EYELINE, "listener"
    resolved = solo_eyeline(t)
    return resolved, ("absorbed" if resolved == _ABSORBED_EYELINE else "authored")


def decamera_action(action: str | None) -> str | None:
    """Boards leak camera-referential staging into ACTION text ("she is now
    closer to the camera") — rendered literally that pulls a straight
    into-the-lens stare. Rewrite the camera as the viewer and pin the eyeline
    off the lens; camera-free actions pass through untouched."""
    if not action or not _ACTION_CAMERA_RE.search(action):
        return action
    out = _ACTION_CAMERA_RE.sub("the viewer", action).rstrip()
    sep = "" if out.endswith((".", "!", "?", ";")) else ";"
    return f"{out}{sep} eyes stay just off-camera, never into the lens"


class ScenePromptCraft:
    SHOT_VOCABULARY = {
        "ECU": "extreme close-up", "CU": "close-up", "MCU": "medium close-up",
        "MS": "medium shot", "FS": "full shot", "LS": "long shot",
        "EWS": "extreme wide establishing shot", "POV": "point-of-view shot", "OTS": "over-the-shoulder shot",
    }

    LIGHTING_VOCABULARY = {
        "DRAMATIC_SIDE": "dramatic side lighting casting half the face in shadow",
        "GOLDEN_HOUR": "warm golden hour sunlight from low angle",
        "NATURAL": "soft natural diffused daylight",
        "NEON": "neon light reflections in rain-slicked surfaces",
        "NIGHT": "dark night scene with minimal ambient light",
        "OVERCAST": "flat overcast diffused light",
        "PRACTICAL": "practical interior lighting from visible sources",
        "BLUE_HOUR": "cool blue twilight",
    }

    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("scene_prompt_craft.txt")

    async def craft(
        self,
        shot: dict,
        character_visuals: dict,
        target_model: str = "wan",
        style_bible: dict | None = None,
        scene_setting: dict | None = None,
        prev_action: str | None = None,
        next_action: str | None = None,
        prev_frame_report: str | None = None,
        foreground_characters: list | None = None,
        blocking: dict | None = None,
        lipsync: bool = False,
        native_talk: bool = False,
        speaker: str = "",
        bridge_from_prev: bool = False,
        image_legend: str = "",
        environment: dict | None = None,
        to_wan: bool = False,
        excluded_species: list | None = None,
    ) -> dict:
        # camera-referential staging in ACTION text renders as a lens stare —
        # scrub it before ANY block (body, blocking, continuity) is assembled
        shot = dict(shot)
        shot["action"] = decamera_action(shot.get("action"))
        prev_action = decamera_action(prev_action)
        next_action = decamera_action(next_action)
        # a SYNTHETIC hold (re-orient wide, silent held beat, establishing or
        # atmosphere insert) exists to HOLD the moment — telling it the next
        # shot's action made the model pre-perform it (the watch press and
        # vanish played inside the hold, then again in its own shot)
        synthetic_hold = bool(re.search(
            r"re-orient wide|held beat|establishing shot|atmosphere cutaway",
            str(shot.get("notes") or ""), re.I))
        if synthetic_hold:
            next_action = None
        # THE PLATE IS THE BOSS for hair: when a character's reference plate
        # rides this shot (the [Image N] legend names them), textual hair
        # length must not overrule the image — rewrite it to defer BEFORE the
        # body, the identity pins and the negative are built, so nothing
        # downstream re-states a conflicting length ("chin-length" text vs a
        # long-haired plate rendered the drama's hair wrong every shot).
        legend_up = (image_legend or "").upper()
        if legend_up and character_visuals:
            character_visuals = {
                k: (_defer_hair_to_image(v)
                    if str(k).strip().upper() in legend_up else v)
                for k, v in character_visuals.items()
            }
        # A location named after a character ("Bear's apartment") must not smuggle
        # the character-noun into the background — strip names from the setting text
        # before it reaches the model, or it renders the animal, not the room.
        names = list(character_visuals.keys())
        if scene_setting:
            clean_setting = dict(scene_setting)
            if clean_setting.get("location"):
                clean_setting["location"] = strip_character_names(
                    clean_setting["location"], names) or "interior room"
            if clean_setting.get("set_items"):
                clean_setting["set_items"] = [
                    strip_character_names(str(it), names) for it in clean_setting["set_items"]
                ]
        else:
            clean_setting = None
        setting_block = (
            f"Scene setting (rule 13 — render this SAME room and these SAME props):\n"
            f"{json.dumps(clean_setting, ensure_ascii=False)}\n\n"
            if clean_setting else ""
        )
        # Adjacent-shot context (rule 14) so the prompt shows only THIS shot's
        # incremental motion instead of replaying the previous shot's action.
        continuity_parts = []
        if prev_frame_report:
            # ground truth beats intention: a VL model read the previous
            # clip's ACTUAL final frame, so the opening state continues from
            # what really rendered, not what the board hoped had rendered
            continuity_parts.append(
                "The previous clip actually ENDED like this (read from its "
                f"final frame): {prev_frame_report}")
        if prev_action:
            # the previous frame is a FROZEN snapshot: a shot that ended
            # mid-motion (walking to the gate) shows a walking pose but nothing
            # says the walk is DONE — the render re-performed the same walk.
            # Declare every previous movement complete and arrived.
            continuity_parts.append(
                f"Previous shot (already shown — do NOT replay this): {prev_action}. "
                "Every movement in it is FINISHED: anyone who was walking, "
                "reaching or turning there has already arrived and now HOLDS "
                "that end position at frame one of this shot. Do not "
                "re-perform, continue or mirror that movement unless THIS "
                "shot's action explicitly asks for it.")
        if bridge_from_prev:
            # the shot-to-shot teleport killer: the clip literally OPENS on
            # the previous shot's last frame (attached as the final reference
            # image), holds it a beat, then moves into this shot's staging as
            # one continuous on-camera transition
            continuity_parts.append(
                "CONTINUITY BRIDGE: this clip OPENS on exactly the "
                "composition of the final reference image (the previous "
                "shot's last frame) — hold that image motionless for the "
                "first half second, then move the camera and subjects into "
                "this shot's staging as ONE continuous move, never a cut.")
        if prev_frame_report or prev_action:
            # each clip renders independently and no frame is chained, so the
            # OPENING pose must be stated or she teleports from sitting to
            # mid-stride between cuts
            continuity_parts.append(
                "OPENING STATE: this shot begins exactly where the previous "
                "clip ended — same positions and postures (someone seated is "
                "STILL seated at frame one). Any change of pose or position "
                "happens ON CAMERA during this shot, never before it — and it "
                "never REPEATS a movement the previous shot already showed.")
        if next_action:
            continuity_parts.append(
                f"Next shot (end this shot where that begins): {next_action}")
        if synthetic_hold:
            continuity_parts.append(
                "HOLD ONLY: no new action begins in this shot - nobody "
                "presses, uses, picks up or reaches for anything; the moment "
                "simply holds, breathing, until the cut.")
        continuity_block = (
            "Continuity with adjacent shots (rule 14):\n"
            + "\n".join(continuity_parts) + "\n\n"
            if continuity_parts else ""
        )
        # Foreground occluders (rule 15): named characters who are only a
        # back/shoulder to camera. Staged as soft-focus foreground, face unseen,
        # so the subject stays the focus.
        # Absolute geometry (rule 12): each subject's depth, screen side,
        # facing and eyeline, resolved by the storyboard and enforced by the
        # stage map — relational verbs never reach the model unresolved.
        blocking_block = ""
        if blocking and blocking.get("subjects"):
            rows = []
            for s in blocking["subjects"]:
                bits = [
                    s.get("frame_position"),
                    # posture is load-bearing: without it the model invents one
                    # ("sitting on the bed" rendered as standing at a window)
                    s.get("posture"),
                    f"screen-{s['screen_side']}" if s.get("screen_side") else None,
                    f"facing {s['facing']}" if s.get("facing") else None,
                    f"eyeline {s['eyeline']}" if s.get("eyeline") else None,
                    # a carried prop threaded across the scene by the stage map:
                    # stated per shot so it never vanishes between cuts
                    f"holding {s['holding']}" if s.get("holding") else None,
                    # a leash/tie threaded by the stage map: without it the rope
                    # rendered lying unattached and the collar flickered
                    (f"on a leash, collar connected to a rope ({s['tethered']})"
                     if s.get("tethered") else None),
                    # the subject's WORLD position, threaded by the stage map —
                    # camera-relative blocking alone let renders relocate people
                    (f"position: {s['anchor']}" if s.get("anchor") else None),
                    decamera_action(s.get("action")),
                ]
                rows.append(f"- {s.get('character')}: " + ", ".join(b for b in bits if b))
            nl = "\n"
            blocking_block = (
                "Blocking (rule 12 — ABSOLUTE positions, follow exactly; this is how "
                "consecutive shots stay in one geometry):" + nl
                + nl.join(rows)
                + (nl + "This shot is a deliberate REVERSE ANGLE."
                   if blocking.get("reverse_angle") else "")
                + nl + nl
            )
        foreground_block = (
            f"Foreground occlusion (rule 15 — show ONLY as a soft-focus back or "
            f"shoulder in the near foreground, face turned away and not visible; "
            f"do NOT make them a co-subject): {json.dumps(list(foreground_characters), ensure_ascii=False)}\n\n"
            if foreground_characters else ""
        )
        # reverse-OTS identity binding: the foreground is an anonymous BACK,
        # and on stylized dramas (no face verification) the model swapped the
        # two people mid-shot. Say by NAME who is the back and who faces.
        fg_binding = bool(foreground_characters and (speaker or "").strip())
        if fg_binding:
            _fgs = ", ".join(str(x) for x in foreground_characters)
            foreground_block += (
                f"IDENTITY BINDING: the near-camera back is {_fgs} and ONLY "
                f"{_fgs}, face never shown; {speaker} is the person FACING "
                f"the camera. The two are distinct people and neither ever "
                f"turns into or becomes the other.\n\n")
        # every listed character exists from frame one: without this, the video
        # model sometimes invents an ARRIVAL — a person rising out of the
        # ground, or popping into existence as the framing tightens
        presence_block = (
            "Presence (rule 20): every listed character is ALREADY in the frame "
            "at the very first frame, fully placed per the blocking. No one "
            "enters, appears, materializes or emerges during the shot unless "
            "the action explicitly describes an entrance.\n\n"
            if character_visuals else ""
        )
        # Per-shot dialogue treatment. A native-talk shot (HappyHorse speaks the
        # line itself — that generated voice IS the delivered audio, there is no
        # TTS overlay) is framed openly talking; every other spoken line hides
        # the mouth (coverage) so an unsynced flapping mouth is never
        # front-and-center, and its words reach the audience through the burned
        # captions. (`lipsync` is a retained-but-inert parameter — the old wan
        # driving-audio path it framed for has been removed.)
        has_line = bool(str(shot.get("dialogue") or "").strip())
        # Mode type tag (Wan's official samples lead with it): a spoken shot is
        # "Single speaker." with one person in frame, "Group conversation." with
        # two or more. A silent / scenery shot leads with no tag.
        type_tag = ""
        if has_line:
            type_tag = ("Single speaker." if len(character_visuals) <= 1
                        else "Group conversation.")
        if has_line and native_talk:
            # HappyHorse native lip-sync: the model speaks the line itself and
            # syncs the mouth to its own generated speech. That voice ships as
            # the clip's real audio (no TTS overlay exists), so the words must
            # be the exact scripted line. Opposite of coverage.
            # In a multi-person shot the delivery text alone never said WHOSE
            # face carries the line, so speakers rendered as the back of a
            # head — pin the named speaker front/three-quarter.
            _who = (speaker or "").strip()
            speaker_face = (
                f" {_who}'s face stays clearly visible to the camera while "
                f"delivering the line — a front or three-quarter view, never "
                f"the back of the head; only a listener may be seen from "
                f"behind." if _who and len(character_visuals) >= 2 else "")
            dialogue_block = (
                "Dialogue delivery (the speaker says THIS line ALOUD on camera: the "
                "character audibly speaks it with natural mouth movement precisely "
                "synced to the spoken words, front-facing and readable is fine, warm "
                "conversational delivery over the full shot. Generate the spoken "
                "dialogue in the character's own voice so the lips match the words."
                + speaker_face
                + " NO on-screen text or subtitles): "
                + json.dumps(str(shot.get("dialogue")), ensure_ascii=False)
                + "\n\n"
            )
        elif has_line:
            dialogue_block = (
                "Dialogue delivery (coverage — this line is spoken OFF a readable mouth: "
                "frame per the blocking as an over-the-shoulder, three-quarter or profile "
                "angle, or favor the LISTENER reacting while the line plays; the speaker's "
                "mouth must never be sharply front-facing and readable. Speech is carried "
                "by gesture, posture and the listener. NO on-screen text or subtitles. "
                "Background audio: ambient sound, sound effects and light musical score "
                "only, with NO spoken voices): "
                + json.dumps(str(shot.get("dialogue")), ensure_ascii=False)
                + "\n\n"
            )
        else:
            dialogue_block = ""
        environment_block = ""
        if environment and environment.get("behavior"):
            environment_block = (
                "Environment reaction (resolved from the world graph, rule 19): "
                f"the surroundings behave like this - {environment['behavior']}.\n"
            )
            if environment.get("suppressed"):
                environment_block += (
                    "Environment suppressed default (the WRONG prior, include its "
                    f"wording in negative_prompt): {environment['suppressed']}.\n"
                )
            environment_block += "\n"
        user_content = (
            f"Shot data:\n{json.dumps(shot)}\n\n"
            f"{blocking_block}"
            f"{presence_block}"
            f"{environment_block}"
            f"{setting_block}"
            f"{continuity_block}"
            f"{foreground_block}"
            f"{dialogue_block}"
            f"Character visual descriptions (use these, NOT names; when a character has outfit_this_shot, dress them EXACTLY in it, that costume overrides any clothing mentioned anywhere else):\n{json.dumps(character_visuals)}\n\n"
            f"Target model: {target_model}\n"
            f"Duration: {shot.get('estimated_duration_seconds', 5)}s\n"
            f"Style bible: {json.dumps(style_bible or {})}"
        )
        if getattr(get_settings(), "cinematic_prompt", False):
            user_content += (
                "\n\nCINEMATIC: Express the given camera_movement as ONE subtle, continuous "
                "camera move with intent and speed (e.g. a slow push-in tightening on the face). "
                "Give the subject CONCRETE motion with amplitude and speed. Name the shot's "
                "diegetic SOUND tied to the action and place (footsteps on wet gravel, a car door "
                "thunking shut, rain on glass, distant traffic). Do NOT invent music or extra voices.\n")
        messages = [
            {"role": "system", "content": self.prompt_template},
            {"role": "user", "content": user_content},
        ]
        result = await self.qwen.chat_json(messages=messages, temperature=0.3, task="prompt_craft")
        if not isinstance(result, dict):
            return {"prompt": "", "negative_prompt": "", "model_parameters": {}}

        # Anti-hallucination guardrails: strip text/numbers/names, force negative prompt.
        sanitizer = PromptSanitizer()
        result["prompt"] = sanitizer.sanitize(
            result.get("prompt", ""), character_names=list(character_visuals.keys())
        )
        # ── Deterministic assembly, in ONE fixed order, DURATION LAST ─────────
        # The model body already leads with the controls (rules 3-4) and now
        # establishes the environment before the characters. Around it we add,
        # in order: front matter (type tag + director TREATMENTS + [Image N]
        # legend), then the model body, then the deterministic clauses (speech,
        # eyelines, setting backstop, Wan sound), then ONE duration sentence at
        # the very end. Every clause is added AFTER sanitization so the [Image N]
        # tokens and the verbatim line survive the text stripper.
        import re as _re
        # strip any duration the model wrote — we own the single final one
        body = _re.sub(r"\s*Duration:?\s*(\d+\s*)?seconds?\.?\s*$", "",
                       result["prompt"], flags=_re.IGNORECASE).rstrip()
        # repair interpolation holes / wardrobe contradictions / mojibake and say
        # so LOUDLY. duration=None: the duration is appended once at the very end,
        # so the repairer must not re-insert its own.
        from app.services.guardrails import validate_and_repair_prompt
        body, repairs = validate_and_repair_prompt(body, None)

        # (1) Native-talk speech: the sanitizer strips quoted words, so re-add the
        # verbatim line here. HappyHorse's generated voice IS the delivered audio
        # (no TTS overlay), so a wrong or mangled line is audible in the final cut.
        speech = ""
        if native_talk and has_line:
            raw = str(shot.get("dialogue") or "").strip()
            # words said ALOUD: strip any (parenthetical) so the model doesn't read
            # the stage direction out loud; the parenthetical becomes the delivery TONE
            spoken = _re.sub(r"\s{2,}", " ",
                             _re.sub(r"\([^)]*\)|（[^）]*）", " ", raw)).strip() or raw
            tone = ", ".join(p.strip() for pair in
                             _re.findall(r"\(([^)]+)\)|（([^）]+)）", raw)
                             for p in pair if p.strip())
            if spoken:
                who = (speaker or "").strip()
                tone_clause = f", {tone}," if tone else ""
                # the clip is LONGER than the line (5s tier for a 4-word line):
                # without a pacing clause the model stretches the delivery to
                # fill the clip and speech comes out unnaturally slow
                pace = (" The line is delivered at a NATURAL conversational pace "
                        "- never slowed or stretched to fill the clip; after the "
                        "line ends they simply hold in the moment, silent.")
                if who:
                    # name the speaker (ties to their [Image N]) and keep everyone
                    # else's mouth still, so the RIGHT person animates in a group shot
                    speech = (f" {who} is the one speaking{tone_clause}: {who} clearly says "
                              f"these exact words aloud with natural lip movement while "
                              f'everyone else keeps a closed, still mouth and listens: "{spoken}"'
                              + pace)
                else:
                    speech = (" The character clearly speaks these exact words aloud"
                              + (f" {tone}" if tone else "") + f': "{spoken}"' + pace)

        # (2) Eyelines — ONLY for characters actually in this frame. Gating to the
        # in-frame cast is what stops a scenery/Wan shot (no in-frame cast) from
        # leaking a named person into the prompt via a stray blocking subject.
        subs = (blocking or {}).get("subjects") if isinstance(blocking, dict) else None
        in_frame_upper = {str(k).strip().upper() for k in character_visuals.keys()}
        _VAGUE_EYELINES = {"camera", "at camera", "the camera", "at the camera",
                           "toward the other character", "off-camera", ""}
        frame_names = [str(k) for k in character_visuals.keys()]

        solo_mode = {"mode": None}

        def _eyeline_text(subj_name, raw) -> str:
            t = str(raw or "").strip()
            # a SOLO subject: vague eyelines become task absorption (the
            # Dora-the-Explorer case), an off-frame PERSON becomes the
            # off-screen listener beside the lens (a conversation's clean
            # single), and authored object eyelines survive untouched
            if len(frame_names) == 1:
                text, mode = resolve_solo_eyeline(t, frame_names)
                solo_mode["mode"] = mode
                return text
            # in a TWO-person shot a vague or camera eyeline locks to the other
            # character — both actors stared into the lens instead of at each
            # other, and "toward the other character" left the model guessing
            if len(frame_names) == 2 and t.lower() in _VAGUE_EYELINES:
                other = next((n for n in frame_names
                              if n.strip().upper() != str(subj_name).strip().upper()), None)
                if other:
                    return f"at {other}"
            # otherwise a literal 'camera' eyeline still never means the lens
            if t.lower() in ("camera", "at camera", "the camera", "at the camera"):
                return "just off-camera, never into the lens"
            return t
        eye = [f"{s.get('character')} looks {_eyeline_text(s.get('character'), s.get('eyeline'))}"
               for s in (subs or [])
               if isinstance(s, dict) and s.get('character') and s.get('eyeline')
               and str(s.get('character')).strip().upper() in in_frame_upper]
        eyelines = (" Eyelines: " + "; ".join(eye) + ".") if eye else ""
        # (2a) SOLO CLAUSE: one person alone in frame is IN the scene, not
        # hosting it. Speaking to an off-screen listener (the conversation's
        # clean single) keeps a near-lens gaze; anything else is absorbed in
        # its own action. Name-free on purpose: Wan-bound prompts carry no
        # reference images, so a name here would be the only name in the
        # text (and there is only one person to mean).
        if len(frame_names) == 1:
            # "to its final frame": clips kept resolving with the subject
            # turning to the lens in the last second
            if solo_mode["mode"] == "listener":
                eyelines += (" The subject is alone in the frame, speaking to "
                             "someone OFF-SCREEN just beside the camera - their "
                             "gaze rests close past the lens, never directly "
                             "into it, for the ENTIRE shot to its final frame, "
                             "and no second person is visible.")
            else:
                eyelines += (" The subject is alone in the frame, absorbed in "
                             "what they are doing for the ENTIRE shot, to its "
                             "final frame - never looking at the camera, no eye "
                             "contact with the viewer.")
        # two-handers ended with BOTH actors rotating to face the lens as the
        # clip resolved — the mutual gaze holds to the last frame
        action_text = str(shot.get("action") or "")
        separation = bool(_EXIT_RE.search(action_text)
                          or _re.search(r"松开|甩开|推开", action_text))
        far_names = [str(s.get("character")) for s in (subs or [])
                     if isinstance(s, dict) and s.get("character")
                     and str(s.get("character")).strip().upper() in in_frame_upper
                     and ("far background" in str(s.get("frame_position") or "").lower()
                          or "far side" in str(s.get("frame_position") or "").lower())]
        if len(frame_names) == 2 and far_names and len(far_names) < 2:
            near = next(n for n in frame_names
                        if n not in far_names)
            far = far_names[0]
            eyelines += (f" {near} faces and looks toward {far} in the "
                         f"distance - angled away from the lens; {far} is far "
                         f"away and small in the frame, never beside {near}.")
        elif len(frame_names) == 2 and not separation:
            eyelines += (" They keep facing and looking at EACH OTHER for the "
                         "ENTIRE shot, to its final frame - neither ever turns "
                         "toward the camera.")
        # a child beside a teen/adult kept rendering at adult height
        eyelines += child_scale_clause(character_visuals)
        # a pet beside people kept inflating (a rabbit at half the girl's
        # height) — pin every creature to its species' true size
        creature_scale = creature_scale_clause(character_visuals)
        eyelines += creature_scale

        # (2b) BACK STAYS BACK: a subject staged facing away (or a foreground
        # occluder) must not rotate to camera mid-shot — continuation models
        # love turning them around, and the revealed face never matches the
        # cast. Stated positively AND banned in the negative below.
        backs = [str(s.get("character"))
                 for s in (subs or [])
                 if isinstance(s, dict) and s.get("character")
                 and str(s.get("facing") or "") == "away-from-camera"
                 and str(s.get("character")).strip().upper() in in_frame_upper]
        for fgc in (foreground_characters or []):
            if str(fgc).strip().upper() in in_frame_upper and str(fgc) not in backs:
                backs.append(str(fgc))
        # an exiting character recedes to the last frame - back to camera,
        # never turning around (the clip-tail lens turn on "runs away")
        exit_sources = " ".join(
            [str(shot.get("action") or "")]
            + [str(s.get("action") or "") for s in (subs or []) if isinstance(s, dict)])
        for ex in exiting_characters(exit_sources, frame_names):
            if ex not in backs:
                backs.append(ex)
        back_clause = ""
        if backs:
            who = ", ".join(backs)
            keeps = "keep" if len(backs) > 1 else "keeps"
            back_clause = (f" {who} {keeps} their back to the camera for the "
                           "entire shot, never turning around, face never shown.")

        # (2c) REACTION FACE: a silent emotional close-up whose whole point is
        # the expression must SAY the face is visible — the frame-handoff's
        # opening state can carry a rear view from the previous shot into a
        # reaction CU and render the back of a head (s3sh2). A deliberate
        # back-shot (facing away / foreground occluder / exit) is respected.
        face_visible = ""
        _beat_now = (str(shot.get("emotional_beat") or "").strip()
                     if isinstance(shot, dict) else "")
        if (len(frame_names) == 1 and _beat_now and not backs
                and str(shot.get("shot_type") or "").upper() in ("CU", "MCU", "ECU")
                and not (has_line and not native_talk)):
            face_visible = (" The subject's face is clearly visible to the "
                            "camera - a front or three-quarter view, never "
                            "the back of the head.")

        # (3) Setting backstop: never a blank background — if the body names none
        # of the scene's setting, add a concise clause (the location plate may
        # have been trimmed from the ref stack).
        setting_clause = ""
        if scene_setting:
            items = [str(i) for i in (scene_setting.get("set_items") or [])][:4]
            loc = str(scene_setting.get("location") or "").strip()
            # ALWAYS restated (not only when the body forgot): the SAME named
            # landmarks in every shot of the scene are what keep the model
            # redrawing the same room — without them each angle invents its
            # own furniture and the backgrounds drift shot to shot
            if loc or items:
                clause = ", ".join([p for p in [loc] + items if p])
                setting_clause = f" Setting: {clause}."

        # (4) Wan sound formula (visual shots only): Wan makes its own diegetic
        # SFX + ambience, never VOICE (dialogue -> HappyHorse). Music splits by
        # what the shot is: a faceless SCENERY beat (establishing/atmosphere)
        # carries its own subtle mood score — that IS where music belongs — but
        # a silent HOLD sits between two spoken lines, where a 3s score swell
        # jars against the talking clips around it.
        wan_sound = ""
        if to_wan and not has_line:
            if character_visuals:
                wan_sound = (" Ambient sound and diegetic sound effects. "
                             "No dialogue. No background music.")
            else:
                mood = str((shot.get("emotional_beat") if isinstance(shot, dict)
                            else None) or "").strip()
                score = ("a subtle atmospheric musical score matching the mood "
                         f"({mood})" if mood else "a subtle atmospheric musical score")
                wan_sound = (f" Rich ambient sound, diegetic sound effects and {score}. "
                             "No dialogue, no voices.")

        # (5) Identity lock (deterministic): the LLM body sometimes paraphrases
        # a character's description and DROPS the identity pins ("no eyewear",
        # "clean-shaven") — the render then follows the reference plate or a
        # trope instead, and glasses/headbands flicker in and out between
        # shots. Re-state per character whatever the body dropped; whatever
        # nobody wears is banned in the negative below.
        identity_clause = ""
        if character_visuals:
            body_low = body.lower()
            # a name may only ride the lock when something else in the prompt
            # already names the character (the [Image N] legend, the speech or
            # eyeline clauses) — a solo shot without those stays nameless
            named_ctx = " ".join([body, image_legend or "", speech, eyelines]).upper()
            locks = []
            for cname, cdesc in character_visuals.items():
                frag = (cdesc.get("video_prompt_fragment")
                        if isinstance(cdesc, dict) else None)
                text = str(frag or cdesc or "").strip()
                outfit = (cdesc.get("outfit_this_shot")
                          if isinstance(cdesc, dict) else None)
                missing = ([p for p in _pin_segments(text)
                            if p.lower() not in body_low] if text else [])
                # headwear lives in the outfit, outside _pin_segments' reach,
                # so pin it here (else the cap flickers shot to shot)
                hw = headwear_pin(text, outfit)
                if hw and hw.lower() not in body_low:
                    missing.append(hw)
                if not missing:
                    continue
                use_name = (len(character_visuals) > 1
                            or str(cname).strip().upper() in named_ctx)
                locks.append((f"{cname}: " if use_name else "")
                             + ", ".join(missing))
            if locks:
                identity_clause = (" Identity lock (IDENTICAL in every shot of "
                                   "this drama): " + "; ".join(locks) + ".")

        # (6) Emotional register: the storyboard's beat ("confusion and hurt")
        # kept dying between the board and the screen — faces rendered neutral.
        # The beat is restated as an ON-FACE instruction, never left implicit.
        emotion_clause = ""
        beat = (str(shot.get("emotional_beat") or "").strip()
                if isinstance(shot, dict) else "")
        if beat and character_visuals:
            emotion_clause = (f" Emotional register: {beat} - clearly visible in "
                              "the cast's facial expressions and posture, never "
                              "neutral or blank faces.")

        # Front matter: the ONE controls statement lives in the model body; here
        # we prepend only the mode TYPE TAG (Wan keys off "Single speaker," /
        # "Group conversation,") and the director TREATMENTS the body won't state
        # (a tilt-shift/time-lapse look, an overall stylization), then the image
        # legend so the model reads the [Image N] map first. lens/composition/
        # light are NOT restated here — the body already carries them from the
        # shot data (they were the duplicate controls statement).
        lead: list[str] = []
        if type_tag:
            lead.append(type_tag)
        dj = shot.get("director_json") if isinstance(shot, dict) else None
        if isinstance(dj, dict):
            treatments = [str(dj[k]).replace("_", "-")
                          for k in ("special_effect", "stylization") if dj.get(k)]
            if treatments:
                t = ", ".join(treatments)
                lead.append(t[:1].upper() + t[1:] + ".")
        front = " ".join(lead)
        if image_legend:
            front = (front + " " + image_legend).strip() if front else image_legend

        # assemble: front matter, model body, deterministic clauses, DURATION last
        dur = int(shot.get("estimated_duration_seconds", 5))
        assembled = ((front + " ") if front else "") + body.lstrip()
        assembled = (assembled.rstrip() + speech + eyelines + back_clause
                     + face_visible + identity_clause + emotion_clause
                     + setting_clause + wan_sound)
        result["prompt"] = assembled.rstrip().rstrip(",") + f" Duration: {dur} seconds."

        if repairs:
            import logging
            logging.getLogger(__name__).warning(
                "prompt repaired before dispatch: %s", "; ".join(repairs))
            result["repairs"] = repairs
        result["negative_prompt"] = sanitizer.inject_negative_prompt(
            result.get("negative_prompt", "")
        )
        if has_line and not native_talk:
            # secondary backstop to the coverage framing above — negatives
            # alone are unreliable, but they bias away from readable lips.
            # Skipped for native_talk: those shots WANT a readable talking mouth.
            result["negative_prompt"] += ", clear front-facing talking mouth close-up"
        if environment and environment.get("suppressed"):
            # deterministic backstop: the overridden location default always
            # lands in the negative, whether or not the model remembered it
            sup = environment["suppressed"]
            if sup.lower() not in (result.get("negative_prompt") or "").lower():
                result["negative_prompt"] += ", " + sup
        if backs:
            result["negative_prompt"] += (
                ", turning around to face the camera, revealing the face")
        if fg_binding:
            result["negative_prompt"] += (
                ", one character turning into another, swapping identities "
                "mid-shot, morphing into a different person")
        if face_visible:
            result["negative_prompt"] += (
                ", back of head, seen from behind, face hidden from camera")
        if len(frame_names) == 1:
            if solo_mode["mode"] == "listener":
                # near-lens gaze is WANTED here — ban only the true lens stare
                # and the listener materializing in frame
                result["negative_prompt"] += (
                    ", staring directly into the lens, breaking the fourth "
                    "wall, second person in frame")
            else:
                # the Dora ban: a solo subject presenting to the audience
                result["negative_prompt"] += (
                    ", looking at the camera, direct eye contact with the viewer, "
                    "breaking the fourth wall, presenting to the camera")
        if len(frame_names) == 2:
            result["negative_prompt"] += (
                ", turning to face the camera, both subjects facing the "
                "viewer, looking into the lens")
        if frame_names:
            # the prev-frame reference kept seeding a SECOND copy of a cast
            # member into the frame (two Lucases in one shot) — ban outright
            result["negative_prompt"] += (
                ", duplicate person, the same person twice, identical twins, "
                "extra copy of a character")
        if creature_scale:
            # the positive clause pins true size; the negative bans the drift
            result["negative_prompt"] += (
                ", giant animal, oversized pet, animal as large as a person")
        # deduped AFTER mapping: 兔 and 兔子 both become "rabbit" — ban it once.
        # a creature deliberately excluded from this shot must not sneak back
        # in as a generic animal painted from a text mention
        for sp_en in dict.fromkeys(_SPECIES_EN.get(str(sp), str(sp))
                                   for sp in (excluded_species or [])):
            result["negative_prompt"] += f", {sp_en}"
        if character_visuals:
            # invented-feature bans (peopled shots): models grow beards on
            # clean-shaven men, glasses and headbands on children, blemishes
            # in close-ups. Each is banned ONLY when no cast description
            # wears it; skin artifacts are never a wardrobe choice, always banned.
            visuals_text = " ".join(str(v) for v in character_visuals.values()).lower()
            if not _re.search(r"beard|moustache|mustache|stubble|facial hair|goatee|"
                              r"胡子|胡须|络腮胡|山羊胡|八字胡",
                              visuals_text):
                result["negative_prompt"] += ", beard, mustache, stubble, facial hair"
            # negation-aware: "no glasses" in a fragment means NOT wearing —
            # the ban must still fire or renders invent specs the text denies
            from app.services.plate_generator import wears_eyewear
            if not wears_eyewear(visuals_text):
                result["negative_prompt"] += (
                    ", eyeglasses, spectacles, glasses on face, sunglasses")
            if not _ACCESSORY_RE.search(visuals_text):
                result["negative_prompt"] += (
                    ", headband, hair accessory, hairpin, hair clip, "
                    "bow in hair, ribbon in hair")
            result["negative_prompt"] += (
                ", acne, pimples, skin blemishes, dark spots on face")
        # Final gate (rule A5): the crafted prompt still carries typographic
        # gremlins — em/en dashes, smart quotes, and the replacement char (mojibake)
        # — which corrupt adjacent words and confuse the video model. Fold them to
        # plain ASCII as the VERY LAST transformation so LLM text AND every appended
        # clause above are cleaned uniformly, just before dispatch.
        def _normtype(s: str) -> str:
            repl = {"—": " - ", "–": " - ", "’": "'", "‘": "'",
                    "“": '"', "”": '"', "�": ""}
            for k, v in repl.items():
                s = s.replace(k, v)
            import re
            return re.sub(r"\s{2,}", " ", s).strip()
        result["prompt"] = _normtype(result.get("prompt", ""))
        result["negative_prompt"] = _normtype(result.get("negative_prompt", ""))
        return result
