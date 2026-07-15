import re

from app.services.qwen_client import QwenClient
from app.services.context_compressor import script_digest
from app.services.prompt_loader import load_prompt
from app.config import get_settings


# A wardrobe change is EARNED only by a real passage of days or a motivated
# change of clothes — never by a mere scene cut. If the script shows none of
# these, every character wears ONE outfit for the whole episode (collapse below).
_EARNED_CHANGE_RE = re.compile(
    r"\b("
    r"next\s+(?:day|morning|evening|night|week|month|year)|"
    r"(?:day|days|week|weeks|month|months|year|years|hour|hours)\s+later|"
    r"the\s+following\s+(?:day|morning|week)|morning\s+after|"
    r"later\s+that\s+(?:night|evening|day)|a\s+(?:day|week|month|year)\s+later|"
    r"time\s+(?:skip|jump)|"
    # motivated changes of clothes
    r"soaked|drenched|change[sd]?\s+(?:into|out\s+of|her|his|their|clothes|outfit)|"
    r"change\s+of\s+clothes|gets?\s+dressed|puts?\s+on\s+(?:a|an|her|his|their)|"
    r"wedding\s+(?:dress|gown)|tuxedo|into\s+a\s+(?:suit|gown|dress|uniform)|"
    r"bandaged|blood-?soaked"
    r")\b", re.IGNORECASE)


def script_earns_wardrobe_change(structured: dict) -> bool:
    """True when the script TEXT signals a real passage of days or a motivated
    change of clothes — the only things that justify a second outfit. Scans
    every scene's heading, description and stage directions. Conservative: no
    signal -> no change -> one outfit per character."""
    for s in (structured or {}).get("scenes") or []:
        directions = s.get("stage_directions") or []
        hay = " ".join([str(s.get("heading") or ""), str(s.get("description") or ""),
                        " ".join(str(d) for d in directions)])
        if _EARNED_CHANGE_RE.search(hay):
            return True
    return False


def collapse_to_single_outfit(planned: dict) -> dict:
    """Merge each character's variants into ONE outfit covering every scene they
    appear in. The primary (default, else first) outfit wins; its scene_numbers
    become the union of all variants'. Stops the planner shipping near-identical
    per-scene outfits — unrealistic (nobody changes shirt between two scenes of
    the same day), a continuity error ('almost the same' reads as a mistake),
    and extra plate cost."""
    collapsed: dict[str, list] = {}
    for name, variants in (planned or {}).items():
        real = [v for v in (variants or []) if isinstance(v, dict)]
        if not real:
            collapsed[name] = variants
            continue
        primary = next((v for v in real if v.get("is_default")), real[0])
        all_scenes = sorted({n for v in real for n in (v.get("scene_numbers") or [])})
        one = dict(primary)
        one["scene_numbers"] = all_scenes
        one["is_default"] = True
        collapsed[name] = [one]
    return collapsed


class WardrobePlanner:
    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("wardrobe_plan.txt")

    async def plan(self, structured: dict, characters: list[dict]) -> dict:
        names = [c.get("name") for c in characters]
        # Wardrobe reads scene-level facts only — the digest drops dialogue and
        # stage directions, cutting prompt tokens on long scripts.
        user = f"Characters: {names}\nScript JSON: {script_digest(structured)}"
        result = await self.qwen.chat_json(messages=[
            {"role": "system", "content": self.prompt_template},
            {"role": "user", "content": user},
        ], temperature=0.3, task="wardrobe")
        out: dict[str, list] = {}
        if isinstance(result, dict):
            for ch in result.get("characters", []):
                out[ch.get("name", "Unknown")] = ch.get("variants", [])
        # Deterministic backstop: unless the script EARNS a change (a real day
        # passage or a motivated change of clothes), collapse to one outfit per
        # character so a fragmented per-scene plan can't ship near-identical
        # outfits. A genuine multi-day story is left as the planner intended.
        if not script_earns_wardrobe_change(structured):
            out = collapse_to_single_outfit(out)
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
