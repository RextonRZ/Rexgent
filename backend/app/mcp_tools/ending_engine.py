import json
from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.config import get_settings


class EndingEngine:
    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("ending_analyse.txt")

    async def analyse(self, script_json: dict, tone_preferences: list[str] | None = None) -> dict:
        messages = [
            {"role": "system", "content": self.prompt_template},
            {"role": "user", "content": json.dumps(script_json)},
        ]
        raw = await self.qwen.chat_json(messages=messages, temperature=0.3)
        if not isinstance(raw, dict):
            raw = {}

        return {
            "has_complete_ending": raw.get("has_ending", False),
            "ending_quality": raw.get("ending_quality", "MISSING"),
            "analysis": {
                "main_conflict_resolved": raw.get("main_conflict_resolved", False),
                "protagonist_arc_complete": raw.get("protagonist_arc_complete", False),
                "emotional_payoff": raw.get("assessment", ""),
                "open_threads": raw.get("open_threads", []),
            },
            "alternatives": raw.get("alternative_endings", []),
        }
