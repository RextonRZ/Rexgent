import json
from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.services.language import language_instruction
from app.config import get_settings


class CharacterExtractor:
    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("character_extract.txt")

    async def extract(self, script_json: dict, language: str = "en") -> list[dict]:
        messages = [
            {"role": "system", "content": self.prompt_template + language_instruction(language)},
            {"role": "user", "content": json.dumps(script_json, ensure_ascii=False)},
        ]
        result = await self.qwen.chat_json(messages=messages, temperature=0.2, task="characters")
        # JSON mode may wrap the array in an object — unwrap it
        return QwenClient.as_list(result)
