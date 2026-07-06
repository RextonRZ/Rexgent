from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.config import get_settings


class AppearanceGenerator:
    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("appearance_generate.txt")

    async def generate(
        self,
        character_name: str,
        role: str,
        personality: str,
        setting: str = "",
        mbti: str = "",
        physical_desc: str = "",
    ) -> dict:
        user_content = (
            f"Character name: {character_name}\n"
            f"Role: {role}\n"
            f"Setting/period: {setting or 'modern'}\n"
            f"Personality: {personality}\n"
            f"MBTI: {mbti or 'unknown'}\n"
            f"Script physical description: {physical_desc or 'none'}"
        )
        messages = [
            {"role": "system", "content": self.prompt_template},
            {"role": "user", "content": user_content},
        ]
        result = await self.qwen.chat_json(messages=messages, temperature=0.5, task="appearance")
        if not isinstance(result, dict):
            return {}
        return result
