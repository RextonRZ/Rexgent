import json
from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.config import get_settings


class StoryboardGenerator:
    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("storyboard_generate.txt")

    async def generate_for_scene(
        self,
        scene_json: dict,
        characters_in_scene: list[dict],
        style_bible: dict | None = None,
    ) -> list[dict]:
        user_content = (
            f"Scene details:\n{json.dumps(scene_json)}\n\n"
            f"Characters involved:\n{json.dumps(characters_in_scene)}\n\n"
            f"Director's style bible:\n{json.dumps(style_bible or {})}"
        )
        messages = [
            {"role": "system", "content": self.prompt_template},
            {"role": "user", "content": user_content},
        ]
        result = await self.qwen.chat_json(messages=messages, temperature=0.5)
        return result if isinstance(result, list) else []
