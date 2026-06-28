from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.config import get_settings


class ScriptGenerator:
    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("script_generate.txt")

    async def generate(
        self,
        genre: str,
        premise: str,
        tone: str = "dramatic",
        episode_count: int = 1,
        target_length: int = 5,
        notes: str = "",
    ) -> str:
        user_prompt = self.prompt_template.format(
            genre=genre,
            premise=premise,
            tone=tone,
            episode_count=episode_count,
            target_length=target_length,
            notes=notes or "None",
        )
        messages = [
            {"role": "user", "content": user_prompt},
        ]
        return await self.qwen.chat(messages=messages, temperature=0.8, max_tokens=8192)
