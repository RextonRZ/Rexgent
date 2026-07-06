from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.services.language import language_instruction
from app.config import get_settings


class ScriptStructurer:
    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.system_prompt = load_prompt("script_structure.txt")

    async def structure(self, raw_text: str, language: str = "en") -> dict:
        system = self.system_prompt + language_instruction(language)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": raw_text},
        ]
        return await self.qwen.chat_json(messages=messages, temperature=0.2, task="structure")
