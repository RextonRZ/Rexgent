import json
from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.services.guardrails import PromptSanitizer, strip_character_names
from app.config import get_settings


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
        image_legend: str = "",
        environment: dict | None = None,
        to_wan: bool = False,
    ) -> dict:
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
            continuity_parts.append(
                f"Previous shot (already shown — do NOT replay this): {prev_action}")
        if prev_frame_report or prev_action:
            # each clip renders independently and no frame is chained, so the
            # OPENING pose must be stated or she teleports from sitting to
            # mid-stride between cuts
            continuity_parts.append(
                "OPENING STATE: this shot begins exactly where the previous "
                "clip ended — same positions and postures (someone seated is "
                "STILL seated at frame one). Any change of pose or position "
                "happens ON CAMERA during this shot, never before it.")
        if next_action:
            continuity_parts.append(
                f"Next shot (end this shot where that begins): {next_action}")
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
                    s.get("action"),
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
            dialogue_block = (
                "Dialogue delivery (the speaker says THIS line ALOUD on camera: the "
                "character audibly speaks it with natural mouth movement precisely "
                "synced to the spoken words, front-facing and readable is fine, warm "
                "conversational delivery over the full shot. Generate the spoken "
                "dialogue in the character's own voice so the lips match the words. "
                "NO on-screen text or subtitles): "
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
            spoken = _re.sub(r"\s{2,}", " ", _re.sub(r"\([^)]*\)", " ", raw)).strip() or raw
            tone = ", ".join(p.strip() for p in _re.findall(r"\(([^)]+)\)", raw) if p.strip())
            if spoken:
                who = (speaker or "").strip()
                tone_clause = f", {tone}," if tone else ""
                if who:
                    # name the speaker (ties to their [Image N]) and keep everyone
                    # else's mouth still, so the RIGHT person animates in a group shot
                    speech = (f" {who} is the one speaking{tone_clause}: {who} clearly says "
                              f"these exact words aloud with natural lip movement while "
                              f'everyone else keeps a closed, still mouth and listens: "{spoken}"')
                else:
                    speech = (" The character clearly speaks these exact words aloud"
                              + (f" {tone}" if tone else "") + f': "{spoken}"')

        # (2) Eyelines — ONLY for characters actually in this frame. Gating to the
        # in-frame cast is what stops a scenery/Wan shot (no in-frame cast) from
        # leaking a named person into the prompt via a stray blocking subject.
        subs = (blocking or {}).get("subjects") if isinstance(blocking, dict) else None
        in_frame_upper = {str(k).strip().upper() for k in character_visuals.keys()}
        def _eyeline_text(raw) -> str:
            # a literal 'camera' eyeline renders as staring into the lens —
            # fourth-wall break. Translate it to a near-lens look instead.
            t = str(raw).strip()
            if t.lower() in ("camera", "at camera", "the camera", "at the camera"):
                return "just off-camera, never into the lens"
            return t
        eye = [f"{s.get('character')} looks {_eyeline_text(s.get('eyeline'))}"
               for s in (subs or [])
               if isinstance(s, dict) and s.get('character') and s.get('eyeline')
               and str(s.get('character')).strip().upper() in in_frame_upper]
        eyelines = (" Eyelines: " + "; ".join(eye) + ".") if eye else ""

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
        back_clause = ""
        if backs:
            who = ", ".join(backs)
            keeps = "keep" if len(backs) > 1 else "keeps"
            back_clause = (f" {who} {keeps} their back to the camera for the "
                           "entire shot, never turning around, face never shown.")

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
        if character_visuals:
            # invented-feature bans (peopled shots): models grow beards on
            # clean-shaven men and blemishes in close-ups. Facial hair is
            # banned ONLY when no cast description wears any (like eyewear);
            # skin artifacts are never a wardrobe choice, always banned.
            visuals_text = " ".join(str(v) for v in character_visuals.values()).lower()
            if not _re.search(r"beard|moustache|mustache|stubble|facial hair|goatee",
                              visuals_text):
                result["negative_prompt"] += ", beard, mustache, stubble, facial hair"
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
