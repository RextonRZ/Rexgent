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
        foreground_block = (
            f"Foreground occlusion (rule 15 — show ONLY as a soft-focus back or "
            f"shoulder in the near foreground, face turned away and not visible; "
            f"do NOT make them a co-subject): {json.dumps(list(foreground_characters), ensure_ascii=False)}\n\n"
            if foreground_characters else ""
        )
        # Dialogue shots must LOOK like talking: the model otherwise renders
        # closed mouths or random extras chattering. Audio stays export's job
        # (TTS overlays there); this rule shapes only the picture.
        dialogue_block = (
            "Dialogue delivery (rule 16 — the speaker is visibly mid-conversation: "
            "natural mouth movement while speaking, conversational gesture, eye "
            "focus on the listener or camera; NO on-screen text or subtitles): "
            f"{json.dumps(str(shot.get('dialogue'))[:160], ensure_ascii=False)}\n\n"
            if str(shot.get("dialogue") or "").strip() else ""
        )
        user_content = (
            f"Shot data:\n{json.dumps(shot)}\n\n"
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
        return result
