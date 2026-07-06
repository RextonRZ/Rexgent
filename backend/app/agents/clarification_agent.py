from app.services.qwen_client import QwenClient
from app.services.context_compressor import script_digest
from app.services.prompt_loader import load_prompt
from app.config import get_settings


class ClarificationAgent:
    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("clarification.txt")

    async def assess(self, structured: dict, characters: list[dict]) -> dict:
        # Ambiguity checks read scene-level facts, not full dialogue — the
        # digest keeps this call cheap on long scripts.
        user = f"Characters: {characters}\nScript: {script_digest(structured)}"
        result = await self.qwen.chat_json(messages=[
            {"role": "system", "content": self.prompt_template},
            {"role": "user", "content": user}], temperature=0.3, task="clarify")
        if not isinstance(result, dict):
            return {"confidence": 1.0, "ambiguities": []}
        result.setdefault("ambiguities", [])
        return result


def needs_pause(assessment: dict, auto_clarify: bool) -> bool:
    return bool(assessment.get("ambiguities")) and not auto_clarify
