import json
from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.config import get_settings


def plan_shot_budget(num_scenes: int, target_length: int) -> tuple[int, int]:
    """Given the scene count and target length (seconds), return how many shots
    per scene and how long each shot should be so the total ≈ target_length."""
    num_scenes = max(1, num_scenes)
    total_budget = max(num_scenes, round(target_length / 5))  # ~5s per shot
    shots_per_scene = max(1, round(total_budget / num_scenes))
    total_shots = shots_per_scene * num_scenes
    shot_seconds = max(2, round(target_length / total_shots))
    return shots_per_scene, shot_seconds


# A clip's length follows what is spoken in it, so a long line isn't crammed into
# 5s. Sized to the tier that fits the line. Capped at 10s: Wan handles 15s but
# HappyHorse's ceiling isn't documented, and long single takes drift the face
# more — raise the top tier once the models are confirmed to accept it.
DURATION_TIERS = (5, 10)
_WORDS_PER_SEC = 2.6  # natural drama delivery pace


def fit_duration_to_dialogue(text: str | None, tiers: tuple = DURATION_TIERS) -> int:
    """Smallest clip tier that comfortably holds the spoken line; the base tier
    for an action beat with no dialogue."""
    words = len((text or "").split())
    if words == 0:
        return tiers[0]
    needed = words / _WORDS_PER_SEC + 0.8  # small pad for breath/pauses
    for t in tiers:
        if needed <= t:
            return t
    return tiers[-1]


class StoryboardGenerator:
    # Never balloon a single scene past this many shots, even if it is very
    # dialogue-heavy — keeps cost and length sane.
    _HARD_CAP = 12

    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("storyboard_generate.txt")

    async def generate_for_scene(
        self,
        scene_json: dict,
        characters_in_scene: list[dict],
        style_bible: dict | None = None,
        max_shots: int = 4,
        shot_seconds: int = 5,
    ) -> list[dict]:
        # Grow the budget so no scripted line is dropped: the scene's dialogue is
        # covered in order, roughly one line (or a short exchange) per shot.
        lines = scene_json.get("dialogue") or []
        cap = min(max(max_shots, len(lines)), self._HARD_CAP)

        user_content = (
            f"Scene details:\n{json.dumps(scene_json, ensure_ascii=False)}\n\n"
            f"Characters involved:\n{json.dumps(characters_in_scene, ensure_ascii=False)}\n\n"
            f"Director's style bible:\n{json.dumps(style_bible or {}, ensure_ascii=False)}\n\n"
            f"This scene has {len(lines)} dialogue line(s). Produce at most {cap} "
            f"shot(s). Preserve EVERY dialogue line verbatim and in order; do not "
            f"invent beats or endings. Clip length is set automatically to fit each "
            f"spoken line, so give each shot the dialogue it should carry."
        )
        messages = [
            {"role": "system", "content": self.prompt_template},
            {"role": "user", "content": user_content},
        ]
        result = await self.qwen.chat_json(messages=messages, temperature=0.4)
        shots = result if isinstance(result, list) else []

        shots = shots[:cap]
        # Clip length follows the spoken line, not a uniform target — a long line
        # gets a longer clip so the video can actually cover it.
        for s in shots:
            if isinstance(s, dict):
                s["estimated_duration_seconds"] = fit_duration_to_dialogue(
                    s.get("dialogue"))
        return shots
