import json
from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.config import get_settings
from app.director.types import ShotPlan


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
            f"shot(s), plus ONE extra shot for each react-then-reveal pair if the "
            f"scene contains an entrance or discovery beat. Preserve EVERY dialogue "
            f"line verbatim and in order; do not invent beats or endings. Clip "
            f"length is set automatically to fit each spoken line, so give each "
            f"shot the dialogue it should carry."
        )
        if getattr(get_settings(), "cinematic_prompt", False):
            user_content += (
                "\n\nCAMERA (choose a `camera_movement` that SERVES the beat; do NOT default to STATIC):\n"
                "- tension / intimacy / a dawning realization -> DOLLY_IN (push in)\n"
                "- isolation / loss / scale -> DOLLY_OUT (pull out)\n"
                "- follow a subject or reveal -> PAN_LEFT/PAN_RIGHT/TILT_UP/TILT_DOWN\n"
                "- a deliberate, held standoff -> STATIC (reserved, never the default)\n"
                "Use HANDHELD/DRONE sparingly. One smooth move per shot.\n")
        messages = [
            {"role": "system", "content": self.prompt_template},
            {"role": "user", "content": user_content},
        ]
        result = await self.qwen.chat_json(messages=messages, temperature=0.4, task="storyboard")
        # JSON mode may wrap the array in an object — unwrap it
        shots = QwenClient.as_list(result)

        shots = shots[:cap]
        # Clip length follows the spoken line, not a uniform target — a long line
        # gets a longer clip so the video can actually cover it.
        for s in shots:
            if isinstance(s, dict):
                s["estimated_duration_seconds"] = fit_duration_to_dialogue(
                    s.get("dialogue"))
        return shots

    async def stage_plan(self, scene_json: dict, characters_in_scene: list[dict],
                         plan: ShotPlan, style_bible: dict | None = None) -> list[dict]:
        """Stager: fill blocking/action/verbatim-dialogue INSIDE a fixed director
        plan. The plan's cinematic choices (size/camera/lens/composition/duration)
        are authoritative and forced after staging. Raises on LLM failure so the
        caller can fall back to generate_for_scene."""
        from app.services.prompt_loader import load_prompt
        lines = scene_json.get("dialogue") or []
        plan_rows = [{
            "shot_number": i + 1, "purpose": s.purpose, "shot_size": s.shot_size,
            "camera_movement": s.camera_movement, "lens": s.lens, "composition": s.composition,
            "covers_lines": s.covers_lines, "action_beat": s.action_beat,
            "blocking_delta": s.blocking_delta,
        } for i, s in enumerate(plan.shots)]
        user_content = (
            f"Scene details:\n{json.dumps(scene_json, ensure_ascii=False)}\n\n"
            f"Characters involved:\n{json.dumps(characters_in_scene, ensure_ascii=False)}\n\n"
            f"Director's style bible:\n{json.dumps(style_bible or {}, ensure_ascii=False)}\n\n"
            f"THE SHOT PLAN (stage each in order; do not change size/camera/lens/composition):\n"
            f"{json.dumps(plan_rows, ensure_ascii=False)}\n\n"
            f"The scene's dialogue lines by index:\n"
            f"{json.dumps({i: l.get('line') for i, l in enumerate(lines)}, ensure_ascii=False)}"
        )
        stage_prompt = load_prompt("storyboard_stage.txt")
        result = await self.qwen.chat_json(
            messages=[{"role": "system", "content": stage_prompt},
                      {"role": "user", "content": user_content}],
            temperature=0.4, task="storyboard_stage")
        staged = QwenClient.as_list(result)
        out: list[dict] = []
        for i, planned in enumerate(plan.shots):
            sd = staged[i] if i < len(staged) and isinstance(staged[i], dict) else {}
            # the plan is authoritative for cinematic intent — force it, don't trust the LLM echo
            sd["shot_number"] = i + 1
            sd["shot_type"] = planned.shot_size
            sd["camera_movement"] = planned.camera_movement
            sd["director_json"] = {
                "purpose": planned.purpose, "lens": planned.lens,
                "composition": planned.composition,
                "light_quality": planned.light_quality,
                "stylization": planned.stylization,
                "special_effect": planned.special_effect,
                "intended_duration": planned.intended_duration,
                "transition_in": planned.transition_in,
                "blocking_delta": planned.blocking_delta,
            }
            # verbatim dialogue for the covered lines, in order (coverage invariant)
            covered = [str(lines[j].get("line")) for j in planned.covers_lines
                       if 0 <= j < len(lines) and lines[j].get("line")]
            sd["dialogue"] = " ".join(covered) if covered else None
            # a dialogue floor so a spoken line is never cut off; else the plan's rhythm
            from app.services.storyboard_generator import fit_duration_to_dialogue
            sd["estimated_duration_seconds"] = (fit_duration_to_dialogue(sd["dialogue"])
                                                if covered else round(planned.intended_duration))
            out.append(sd)
        return out
