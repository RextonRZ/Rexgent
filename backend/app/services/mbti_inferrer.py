import json
from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.config import get_settings


class MBTIInferrer:
    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("mbti_infer.txt")

    async def infer(
        self,
        character_name: str,
        dialogue_samples: list[str],
        personality_summary: str,
        actions_summary: str = "",
    ) -> dict:
        user_content = (
            f"Character name: {character_name}\n"
            f"Dialogue samples: {json.dumps(dialogue_samples)}\n"
            f"Actions and decisions: {actions_summary or 'Not specified'}\n"
            f"Personality summary: {personality_summary}"
        )
        messages = [
            {"role": "system", "content": self.prompt_template},
            {"role": "user", "content": user_content},
        ]
        result = await self.qwen.chat_json(messages=messages, temperature=0.3, task="mbti")
        if not isinstance(result, dict):
            return {"mbti_type": None, "confidence": None}
        return result
