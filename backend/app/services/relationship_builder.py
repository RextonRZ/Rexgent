import json
from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.config import get_settings


class RelationshipBuilder:
    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("relationship_extract.txt")

    async def extract(self, script_json: dict, characters_json: list[dict]) -> list[dict]:
        user_content = (
            f"SCREENPLAY:\n{json.dumps(script_json)}\n"
            f"CHARACTERS:\n{json.dumps(characters_json)}"
        )
        messages = [
            {"role": "system", "content": self.prompt_template},
            {"role": "user", "content": user_content},
        ]
        result = await self.qwen.chat_json(messages=messages, temperature=0.2, task="relationships")
        # JSON mode may wrap the array in an object — unwrap it
        return QwenClient.as_list(result)
