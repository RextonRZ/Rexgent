from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.services.language import language_instruction
from app.config import get_settings


def plan_dialogue_budget(target_length: int | None) -> int:
    """How many dialogue lines fit an episode of `target_length` seconds. A
    line plays ~5s on screen (short line -> 5s clip tier), so ~1 line per 6s
    leaves room for action beats and silence. Floor of 3 so a tiny episode is
    still a drama. Without this the writer paced by feel: a 30s ask produced
    11 lines that boarded to 97s."""
    return max(3, round((target_length or 0) / 6))


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
        development: str = "",
    ) -> str:
        user_prompt = self.prompt_template.format(
            genre=genre,
            premise=premise,
            tone=tone,
            episode_count=episode_count,
            target_length=target_length,
            line_budget=plan_dialogue_budget(target_length),
            notes=notes or "None",
            development=development or "None",
        )
        user_prompt += self.language_instruction(language)
        messages = [
            {"role": "user", "content": user_prompt},
        ]
        return await self.qwen.chat(messages=messages, model=model, temperature=0.8,
                                    max_tokens=8192, task="script")
