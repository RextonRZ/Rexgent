import json
from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.services.guardrails import PromptSanitizer
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
    ) -> dict:
        user_content = (
            f"Shot data:\n{json.dumps(shot)}\n\n"
            f"Character visual descriptions (use these, NOT names):\n{json.dumps(character_visuals)}\n\n"
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
