from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.services.language import language_instruction
from app.config import get_settings


def plan_dialogue_budget(target_length: int | None) -> int:
    """How many dialogue lines fit an episode of `target_length` seconds. A
    line plays ~5s on screen (short line -> 5s clip tier), so ~1 line per 5s
    keeps conversations alive while the duration fitter and the 3s beat floor
    hold the runtime. Floor of 3 so a tiny episode is still a drama. Without
    this the writer paced by feel: a 30s ask produced 11 lines that boarded
    to 97s; the earlier 1-per-6s budget made conversations feel clipped."""
    return max(3, round((target_length or 0) / 5))


def count_dialogue_lines(structured: dict | None) -> int:
    """Total dialogue lines in a structured script (every line becomes ~5s of
    screen time downstream — the coverage invariant boards them all)."""
    return sum(len(sc.get("dialogue_lines") or [])
               for sc in (structured or {}).get("scenes", []))


def over_line_budget(structured: dict | None, target_length: int | None) -> int | None:
    """The budget, when the structured draft exceeds it (one line of grace) —
    the signal to run ONE trim rewrite. None when the draft fits. The prompt
    states the budget, but the writer LLM overshoots it by 2x when the story
    wants more; enforcement has to happen after the draft, not inside it."""
    budget = plan_dialogue_budget(target_length)
    return budget if count_dialogue_lines(structured) > budget + 1 else None


def trim_note(lines: int, budget: int, target_length: int | None) -> str:
    """The revision note for the trim rewrite, phrased like a judge's note so
    the writer keeps the story and cuts only the talk."""
    return (f"REVISION - your previous draft had {lines} lines of dialogue, but a "
            f"{target_length} second episode holds at most {budget}. Rewrite the SAME "
            f"story with at most {budget} dialogue lines in total, each under 15 words. "
            f"Merge or cut lines and let actions carry the rest; keep the hook, the "
            f"escalation and the cliffhanger.")


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
