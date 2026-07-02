from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.config import get_settings


class WardrobePlanner:
    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("wardrobe_plan.txt")

    async def plan(self, structured: dict, characters: list[dict]) -> dict:
        names = [c.get("name") for c in characters]
        user = f"Characters: {names}\nScript JSON: {structured}"
        result = await self.qwen.chat_json(messages=[
            {"role": "system", "content": self.prompt_template},
            {"role": "user", "content": user},
        ], temperature=0.3)
        out: dict[str, list] = {}
        if isinstance(result, dict):
            for ch in result.get("characters", []):
                out[ch.get("name", "Unknown")] = ch.get("variants", [])
        return out


def map_variant_for_scene(variants: list[dict], scene_number: int) -> dict | None:
    """Pick the costume variant whose scene_numbers contains scene_number; else the default; else first."""
    if not variants:
        return None
    for v in variants:
        if scene_number in (v.get("scene_numbers") or []):
            return v
    for v in variants:
        if v.get("is_default"):
            return v
    return variants[0]
