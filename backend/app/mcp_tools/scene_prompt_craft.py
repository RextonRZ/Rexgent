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
        if prev_action:
            continuity_parts.append(
                f"Previous shot (already shown — do NOT replay this): {prev_action}")
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
        # the anti-text number-stripper eats the duration digit ("Duration:
        # seconds."); restate it AFTER sanitization so the pacing hint survives
        import re as _re
        cleaned = _re.sub(r"\s*Duration:?\s*(\d+\s*)?seconds?\.?\s*$", "",
                          result["prompt"], flags=_re.IGNORECASE).rstrip()
        result["prompt"] = (
            f"{cleaned} Duration: {shot.get('estimated_duration_seconds', 5)} seconds."
        )
        # the last gate: repair interpolation holes, wardrobe contradictions,
        # replacement chars — and say so LOUDLY instead of shipping quietly
        from app.services.guardrails import validate_and_repair_prompt
        result["prompt"], repairs = validate_and_repair_prompt(
            result["prompt"], shot.get("estimated_duration_seconds", 5))
        # Native-talk shots must SPEAK the exact scripted line, but the text
        # sanitizer above strips quoted words (to keep on-screen text out) and
        # eats the dialogue with them. Re-append the verbatim line AFTER all
        # stripping so HappyHorse speaks the real words — its generated voice
        # ships as the clip's delivered audio (no TTS overlay), so a wrong or
        # mangled line here is audible in the final cut.
        if native_talk and has_line:
            import re as _re
            raw = str(shot.get("dialogue") or "").strip()
            # words said ALOUD: strip any (parenthetical) so the model does not read
            # the stage direction out loud; the parenthetical becomes the delivery TONE
            spoken = _re.sub(r"\s{2,}", " ", _re.sub(r"\([^)]*\)", " ", raw)).strip() or raw
            tone = ", ".join(p.strip() for p in _re.findall(r"\(([^)]+)\)", raw) if p.strip())
            if spoken:
                who = (speaker or "").strip()
                # a distinct TONE label (Alibaba's multi-character principle 3) so the
                # native voice is delivered WITH emotion, not flat
                tone_clause = f", {tone}," if tone else ""
                if who:
                    # name the speaker (ties to their [Image N] in the legend) and
                    # keep everyone else's mouth still, so HappyHorse animates the
                    # RIGHT person in a multi-character shot
                    result["prompt"] = (
                        result["prompt"].rstrip()
                        + f" {who} is the one speaking{tone_clause}: {who} clearly says these "
                          f"exact words aloud with natural lip movement while everyone else "
                          f'keeps a closed, still mouth and listens: "{spoken}"'
                    )
                else:
                    result["prompt"] = (
                        result["prompt"].rstrip()
                        + " The character clearly speaks these exact words aloud"
                        + (f" {tone}" if tone else "")
                        + f': "{spoken}"'
                    )
        # Eyeline: the blocking's eyelines are authoritative — append them so
        # faces look where the shot staged them instead of at the camera.
        subs = (blocking or {}).get("subjects") if isinstance(blocking, dict) else None
        eye = [f"{s.get('character')} looks {s.get('eyeline')}"
               for s in (subs or []) if isinstance(s, dict) and s.get('character') and s.get('eyeline')]
        if eye:
            result["prompt"] = result["prompt"].rstrip() + " Eyelines: " + "; ".join(eye) + "."
        # Environment: never render a blank background — if the crafted prompt
        # names none of the scene's setting, append a concise setting clause
        # (matters most when the location plate was trimmed from the ref stack).
        if scene_setting:
            items = [str(i) for i in (scene_setting.get("set_items") or [])][:4]
            loc = str(scene_setting.get("location") or "").strip()
            hay = result["prompt"].lower()
            named = (loc and loc.lower() in hay) or any(it.lower()[:15] in hay for it in items)
            if not named and (loc or items):
                clause = ", ".join([p for p in [loc] + items if p])
                result["prompt"] = result["prompt"].rstrip() + f" Setting: {clause}."
        if image_legend:
            # prepend AFTER sanitization so the [Image N] tokens survive the text
            # stripper; leads the prompt so the model reads the mapping first
            result["prompt"] = image_legend + " " + result["prompt"].lstrip()
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
        # Director controls-first (Alibaba pattern): PREPEND a model-honored
        # comma-list of technical controls (light quality, lens, composition)
        # ahead of the scene, so the model reads the optics before the action.
        # Placed after sanitization, before the typographic normalizer, so the
        # clause survives the text stripper — same idiom as the image_legend prefix.
        dj = shot.get("director_json") if isinstance(shot, dict) else None
        if isinstance(dj, dict):
            ctrl = []
            # special_effect leads (a tilt-shift/time-lapse treatment frames the whole shot)
            if dj.get("special_effect"):
                ctrl.append(str(dj["special_effect"]).replace("_", "-"))
            lq = dj.get("light_quality")
            if lq:
                ctrl.append(f"{lq} light")
            if dj.get("lens"):
                ctrl.append(f"{dj['lens']} lens")
            if dj.get("composition"):
                ctrl.append(dj["composition"].replace("_", "-") + " composition")
            # stylization closes the control list (the overall aesthetic treatment)
            if dj.get("stylization"):
                ctrl.append(str(dj["stylization"]).replace("_", "-"))
            if ctrl:
                prefix = ", ".join(ctrl)
                prefix = prefix[:1].upper() + prefix[1:] + ". "
                result["prompt"] = prefix + result["prompt"].lstrip()
        # Wan sound formula (visual shots only): Wan generates its OWN diegetic
        # SFX + ambience, but never VOICE (dialogue routes to HappyHorse — resolved
        # decision 3) and never per-clip MUSIC (one episode track owns BGM —
        # resolved decision 1). Appended at the tail, after sanitization, so it
        # survives the text stripper and lands deterministically before dispatch.
        # Skipped for HappyHorse shots and for any shot that carries a line.
        if to_wan and not has_line:
            result["prompt"] = (
                result["prompt"].rstrip()
                + " Ambient sound and diegetic sound effects. "
                  "No dialogue. No background music."
            )
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
