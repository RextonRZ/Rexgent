"""Story development: the writers'-room step BEFORE the script. A 200-character
premise is a situation, not a story — this turns it into a dramatic spine
(conflict, a charged relationship, a secret, a mid-story turn) so the
screenwriter writes from a real brief instead of padding a thin idea. The
user still types one sentence; the AI does the "what if" work."""
import logging

from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.services.language import language_instruction
from app.config import get_settings

logger = logging.getLogger(__name__)


class StoryDeveloper:
    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("story_develop.txt")

    async def develop(self, premise: str, genre: str, tone: str = "dramatic",
                      episode_count: int = 1, language: str = "en") -> dict:
        """Returns the treatment dict, or {} if development is unavailable —
        the screenwriter always still works from the bare premise, so a flaky
        development call degrades the quality, never blocks the drama."""
        try:
            user_prompt = self.prompt_template.format(
                premise=premise, genre=genre, tone=tone, episode_count=episode_count,
            ) + language_instruction(language)
            result = await self.qwen.chat_json(
                messages=[{"role": "user", "content": user_prompt}],
                model="qwen-max", temperature=0.9, task="develop")
            return result if isinstance(result, dict) and result.get("logline") else {}
        except Exception as e:  # noqa: BLE001 — development is enrichment, not a gate
            logger.warning("story development skipped (writing from bare premise): %s", e)
            return {}

    @staticmethod
    def as_brief(treatment: dict) -> str:
        """Fold the treatment into a brief the script prompt honors. Empty
        string when there's no treatment, so the prompt reads 'None'."""
        if not treatment:
            return ""
        lines = []
        if treatment.get("logline"):
            lines.append(f"Logline: {treatment['logline']}")
        if treatment.get("central_conflict"):
            lines.append(f"Central conflict: {treatment['central_conflict']}")
        rel = treatment.get("key_relationship") or {}
        if rel.get("between") or rel.get("tension"):
            lines.append(f"Key relationship ({rel.get('between', '')}): {rel.get('tension', '')}")
        if treatment.get("the_secret"):
            lines.append(f"The secret the audience uncovers: {treatment['the_secret']}")
        if treatment.get("stakes"):
            lines.append(f"Real stakes: {treatment['stakes']}")
        if treatment.get("the_turn"):
            lines.append(f"The mid-story turn (drives the cliffhanger): {treatment['the_turn']}")
        if treatment.get("why_now"):
            lines.append(f"Why it collides now: {treatment['why_now']}")
        cast = treatment.get("cast") or []
        if cast:
            lines.append("Cast: " + "; ".join(str(c) for c in cast))
        return "\n".join(lines)

    @staticmethod
    def headline(treatment: dict) -> str:
        """A short label for the crew node artifact — the turn is the payoff."""
        if not treatment:
            return "wrote from the premise as-is"
        turn = (treatment.get("the_turn") or treatment.get("logline") or "").strip()
        return (turn[:90] + "…") if len(turn) > 90 else (turn or "developed")
