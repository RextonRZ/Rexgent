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


class StoryboardGenerator:
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
        user_content = (
            f"Scene details:\n{json.dumps(scene_json)}\n\n"
            f"Characters involved:\n{json.dumps(characters_in_scene)}\n\n"
            f"Director's style bible:\n{json.dumps(style_bible or {})}\n\n"
            f"Produce at most {max_shots} shot(s) for this scene, each about "
            f"{shot_seconds} seconds. Keep it tight — no filler shots."
        )
        messages = [
            {"role": "system", "content": self.prompt_template},
            {"role": "user", "content": user_content},
        ]
        result = await self.qwen.chat_json(messages=messages, temperature=0.5)
        shots = result if isinstance(result, list) else []

        # Hard-cap so the storyboard can't exceed the target length.
        shots = shots[:max_shots]
        for s in shots:
            if isinstance(s, dict):
                raw = s.get("estimated_duration_seconds", shot_seconds)
                try:
                    dur = int(raw)
                except (TypeError, ValueError):
                    dur = shot_seconds
                s["estimated_duration_seconds"] = max(2, min(shot_seconds, dur))
        return shots
