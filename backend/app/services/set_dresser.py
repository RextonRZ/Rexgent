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
import re
from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.config import get_settings

_TEXT_PROP = re.compile(r"\b(reading|labeled|labelled|marked|says|sign|number(s)?|"
                        r"letters|written|inscription|plate\s+reading)\b", re.I)
_QUOTED = re.compile(r"['\"‘’“”].*?['\"‘’“”]")


def _strip_readable_text(items: list) -> list:
    """Drop props whose specific TEXT matters (signs, mailbox numbers, labels) —
    AI video can't render legible text and it corrupts nearby words in the prompt.
    Also scrub any stray quoted text off the props that remain."""
    out = []
    for it in items:
        s = str(it)
        if _TEXT_PROP.search(s):
            continue
        out.append(_QUOTED.sub("", s).strip())
    return [i for i in out if i]


class SetDresser:
    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("set_dress.txt")

    async def dress(self, scene: dict, shots: list[dict],
                    cast_names: list | None = None) -> dict:
        user = (
            f"Scene:\n{json.dumps(scene, ensure_ascii=False)}\n\n"
            f"Shots:\n{json.dumps(shots, ensure_ascii=False)}"
        )
        # The dresser sees the action text but not the cast, so a character whose
        # NAME reads like an object (a pet 雪球 / "Snowball") gets dressed as a
        # prop. Naming the scene's living characters forbids that outright.
        names = [str(n).strip() for n in (cast_names or []) if str(n).strip()]
        if names:
            user += ("\n\nCHARACTERS present in this scene — these are LIVING "
                     "characters (people and animals/pets) handled by casting. "
                     "NEVER output any of them, or a paraphrase of them, as a "
                     "set_item, prop or hero prop, even if a name reads like an "
                     "object (a pet named 'Snowball' is a living animal, not a "
                     f"ball): {json.dumps(names, ensure_ascii=False)}")
        result = await self.qwen.chat_json(messages=[
            {"role": "system", "content": self.prompt_template},
            {"role": "user", "content": user},
        ], temperature=0.2, task="set_dress")
        if not isinstance(result, dict):
            return {"set_items": [], "state_changes": []}
        items = _strip_readable_text([str(i) for i in (result.get("set_items") or []) if i])
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
