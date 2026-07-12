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
        environment: dict | None = None,
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
        # Per-shot dialogue treatment, two modes. A shot whose mouth will be
        # DRIVEN by its own line (wan driving_audio) is framed openly talking;
        # every other spoken line hides the mouth (coverage) so an unsynced
        # flapping mouth is never front-and-center. Audio itself stays
        # export's job (TTS overlays there); this shapes only the picture.
        has_line = bool(str(shot.get("dialogue") or "").strip())
        if has_line and lipsync:
            dialogue_block = (
                "Dialogue delivery (rule 10 applied to THIS shot — the speaker is visibly mid-conversation: "
                "natural mouth movement while speaking, conversational gesture, eye "
                "focus on the listener or camera; NO on-screen text or subtitles. "
                "Background audio: ambient sound, sound effects and light musical "
                "score only, with NO spoken voices): "
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
        result["negative_prompt"] = sanitizer.inject_negative_prompt(
            result.get("negative_prompt", "")
        )
        if has_line and not lipsync:
            # secondary backstop to the coverage framing above — negatives
            # alone are unreliable, but they bias away from readable lips
            result["negative_prompt"] += ", clear front-facing talking mouth close-up"
        if environment and environment.get("suppressed"):
            # deterministic backstop: the overridden location default always
            # lands in the negative, whether or not the model remembered it
            sup = environment["suppressed"]
            if sup.lower() not in (result.get("negative_prompt") or "").lower():
                result["negative_prompt"] += ", " + sup
        return result
