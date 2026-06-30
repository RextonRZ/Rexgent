from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.services.language import language_instruction
from app.config import get_settings


class ScriptGenerator:
    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("script_generate.txt")

    @staticmethod
    def language_instruction(language: str) -> str:
        return language_instruction(language)

    async def generate(
        self,
        genre: str,
        premise: str,
        tone: str = "dramatic",
        episode_count: int = 1,
        target_length: int = 30,  # seconds
        notes: str = "",
        language: str = "en",
        model: str = "qwen-max",
    ) -> str:
        user_prompt = self.prompt_template.format(
            genre=genre,
            premise=premise,
            tone=tone,
            episode_count=episode_count,
            target_length=target_length,
            notes=notes or "None",
        )
        user_prompt += self.language_instruction(language)
        messages = [
            {"role": "user", "content": user_prompt},
        ]
        return await self.qwen.chat(messages=messages, model=model, temperature=0.8, max_tokens=8192)
