"""Set dressing: pin the background down per scene.

Each clip is an independent generation, so without help the model invents a
new table and a new vase every shot. The set dresser derives, once per scene,
the props that must stay identical across its shots — plus any prop STATE
changes the action causes (a vase breaks in shot 3, so shots 4+ must show it
broken, never restored). Prompt crafting injects this into every shot of the
scene; the generation runner also drops the (now outdated) location plate
once the state has changed.
"""
import json
from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.config import get_settings


class SetDresser:
    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("set_dress.txt")

    async def dress(self, scene: dict, shots: list[dict]) -> dict:
        user = (
            f"Scene:\n{json.dumps(scene, ensure_ascii=False)}\n\n"
            f"Shots:\n{json.dumps(shots, ensure_ascii=False)}"
        )
        result = await self.qwen.chat_json(messages=[
            {"role": "system", "content": self.prompt_template},
            {"role": "user", "content": user},
        ], temperature=0.2, task="set_dress")
        if not isinstance(result, dict):
            return {"set_items": [], "state_changes": []}
        items = [str(i) for i in (result.get("set_items") or []) if i]
        changes = [c for c in (result.get("state_changes") or [])
                   if isinstance(c, dict) and c.get("state")]
        return {"set_items": items, "state_changes": changes}


def setting_for_shot(set_json: dict | None, location: str | None,
                     shot_number: int) -> tuple[dict | None, bool]:
    """The scene setting a given shot must render, and whether the set state
    has already changed by this shot (in which case the pristine location
    plate would contradict the story and should not be anchored).

    Returns (scene_setting | None, state_changed)."""
    ctx = set_json or {}
    applied = [c.get("state") for c in (ctx.get("state_changes") or [])
               if isinstance(c, dict) and c.get("state")
               and (c.get("from_shot") or 10 ** 9) <= (shot_number or 0)]
    items = ctx.get("set_items") or []
    if not items and not applied and not location:
        return None, False
    setting = {"location": location or "", "set_items": items}
    if applied:
        setting["current_state"] = applied
    return setting, bool(applied)
