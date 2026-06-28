import json
from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.config import get_settings


class CharacterExtractor:
    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("character_extract.txt")

    async def extract(self, script_json: dict) -> list[dict]:
        messages = [
            {"role": "system", "content": self.prompt_template},
            {"role": "user", "content": json.dumps(script_json)},
        ]
        result = await self.qwen.chat_json(messages=messages, temperature=0.2)
        if not isinstance(result, list):
            return []
        return result
