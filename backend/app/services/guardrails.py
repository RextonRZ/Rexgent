import re
import json
import logging
from collections import Counter

logger = logging.getLogger(__name__)


class PromptSanitizer:
    """Prevents text/number hallucination in generated video.

    Wan/HappyHorse render quoted text, scene numbers, and digits as garbled
    glyphs. This strips them and forces an anti-text negative prompt.
    """

    MANDATORY_NEGATIVE = (
        "text, words, letters, numbers, subtitles, watermark, logo, title card, "
        "signs, writing, captions, credits, UI, HUD, overlay, readable text, font, "
        "typography, printed, handwritten, digital display, screen text, label"
    )

    SCENE_LABEL_PATTERN = re.compile(
        r"\b(Scene|Act|INT\.|EXT\.|SCENE|ACT)\s*\d*[:\.\-]?\s*", re.IGNORECASE
    )
    # List markers at line start OR inline (", 2. ", " 3) ") — requires trailing
    # whitespace so decimals like "5.5" are never touched.
    NUMBERING_PATTERN = re.compile(r"(?:^|\s)\d+[\.\)]\s+", re.MULTILINE)
    QUOTED_TEXT_PATTERN = re.compile(r"[\"“”][^\"“”]{2,}[\"“”]")
    SINGLE_QUOTED_PATTERN = re.compile(r"['‘’][^'‘’]{2,}['‘’]")
    YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
    NUMBER_GROUP_PATTERN = re.compile(
        r"\b(\d+)\s+(people|persons|characters|figures|men|women|cops|officers|soldiers|guards)"
    )
    STANDALONE_NUMBER_PATTERN = re.compile(r"\b\d{2,}\b")
    URL_PATTERN = re.compile(r"https?://\S+")

    NUMBER_REPLACEMENTS = {
        "2": "a pair of", "3": "a small group of", "4": "a small group of",
        "5": "several", "6": "several", "7": "a group of",
        "8": "a group of", "9": "a group of", "10": "many",
    }

    def sanitize(self, prompt: str, character_names: list[str] | None = None) -> str:
        result = prompt
        result = self.QUOTED_TEXT_PATTERN.sub("", result)
        result = self.SINGLE_QUOTED_PATTERN.sub("", result)
        result = self.SCENE_LABEL_PATTERN.sub("", result)
        result = self.NUMBERING_PATTERN.sub(" ", result)
        result = self.URL_PATTERN.sub("", result)
        result = self.YEAR_PATTERN.sub("", result)

        def replace_number_group(match):
            num, noun = match.group(1), match.group(2)
            return f"{self.NUMBER_REPLACEMENTS.get(num, 'a group of')} {noun}"

        result = self.NUMBER_GROUP_PATTERN.sub(replace_number_group, result)
        result = self.STANDALONE_NUMBER_PATTERN.sub("", result)

        if character_names:
            for name in character_names:
                result = re.sub(r"\b" + re.escape(name) + r"\b", "", result, flags=re.IGNORECASE)

        result = re.sub(r"\s{2,}", " ", result).strip()
        result = re.sub(r",\s*,", ",", result)
        result = result.strip(", ")
        return result

    def get_mandatory_negative_prompt(self) -> str:
        return self.MANDATORY_NEGATIVE

    def inject_negative_prompt(self, existing_negative: str = "") -> str:
        if existing_negative:
            return f"{existing_negative}, {self.MANDATORY_NEGATIVE}"
        return self.MANDATORY_NEGATIVE


class JsonOutputValidator:
    """Hardening for Qwen-Max JSON responses."""

    def clean_and_parse(self, raw: str):
        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        cleaned = re.sub(r",\s*}", "}", cleaned)
        cleaned = re.sub(r",\s*]", "]", cleaned)
        return json.loads(cleaned)

    def is_truncated(self, raw: str) -> bool:
        cleaned = raw.strip()
        open_braces = cleaned.count("{") - cleaned.count("}")
        open_brackets = cleaned.count("[") - cleaned.count("]")
        return open_braces > 0 or open_brackets > 0

    def detect_prompt_leakage(self, response: str, system_prompt: str, min_match_len: int = 30) -> bool:
        rl, pl = response.lower(), system_prompt.lower()
        for i in range(max(0, len(pl) - min_match_len)):
            if pl[i:i + min_match_len] in rl:
                logger.warning("Prompt leakage detected in model response")
                return True
        return False

    def detect_repetition(self, data, threshold: int = 3) -> bool:
        values = self._extract_strings(data)
        counts = Counter(v for v in values if len(v) > 10)
        for value, count in counts.items():
            if count >= threshold:
                logger.warning(f"Repetition detected: '{value[:40]}...' x{count}")
                return True
        return False

    def _extract_strings(self, obj, results=None) -> list[str]:
        if results is None:
            results = []
        if isinstance(obj, str):
            results.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                self._extract_strings(v, results)
        elif isinstance(obj, list):
            for item in obj:
                self._extract_strings(item, results)
        return results


class CostCircuitBreaker:
    def __init__(self, budget: float = 40.0, reserve_pct: float = 0.15,
                 shot_cap: float = 2.0, max_retries: int = 15):
        self.budget = budget
        self.ceiling = budget * (1 - reserve_pct)
        self.shot_cap = shot_cap
        self.max_retries = max_retries

    def should_stop(self, current_cost: float) -> bool:
        return current_cost >= self.ceiling

    def exceeds_shot_cap(self, estimated_cost: float) -> bool:
        return estimated_cost > self.shot_cap

    def retries_exhausted(self, total_retries: int) -> bool:
        return total_retries > self.max_retries

    def remaining(self, current_cost: float) -> float:
        return max(0.0, self.ceiling - current_cost)


class InputSanitizer:
    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(previous|above|all)\s+(instructions|prompts|rules)", re.IGNORECASE),
        re.compile(r"disregard\s+(previous|above|all|everything)", re.IGNORECASE),
        re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
        re.compile(r"\b(SYSTEM|ASSISTANT|USER)\s*:", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\b", re.IGNORECASE),
        re.compile(r"act\s+as\s+(if\s+you\s+are|a)\b", re.IGNORECASE),
        re.compile(r"pretend\s+to\s+be\b", re.IGNORECASE),
        re.compile(r"from\s+now\s+on\s+you\b", re.IGNORECASE),
    ]

    def sanitize(self, text: str, max_length: int = 1000) -> str:
        result = text
        for pattern in self.INJECTION_PATTERNS:
            m = pattern.search(result)
            if m:
                logger.warning(f"Prompt injection stripped: '{m.group()}'")
                result = pattern.sub("", result)
        result = result.strip()
        if len(result) > max_length:
            result = result[:max_length]
        return result


class PreGenerationValidator:
    def validate(self, characters: list[dict], shots: list[dict]) -> dict:
        issues: list[str] = []
        missing_visuals: list[str] = []

        if not shots:
            return {"pass": False, "issues": ["No shots in storyboard"], "missing_visuals": [],
                    "total_shots": 0, "total_duration": 0}

        names_in_shots = set()
        for shot in shots:
            for name in (shot.get("characters_in_frame") or []):
                names_in_shots.add(name)

        char_map = {c["name"]: c for c in characters}
        for name in names_in_shots:
            c = char_map.get(name)
            if not c:
                missing_visuals.append(f"{name}: not found in database")
            elif not c.get("video_prompt_fragment") and not c.get("visual_description"):
                missing_visuals.append(f"{name}: no visual description")

        if missing_visuals:
            issues.append(f"{len(missing_visuals)} character(s) missing visual descriptions")

        total_duration = sum(s.get("estimated_duration_seconds", 0) for s in shots)
        if total_duration <= 0:
            issues.append("Total estimated duration is 0")

        return {
            "pass": len(issues) == 0,
            "issues": issues,
            "missing_visuals": missing_visuals,
            "total_shots": len(shots),
            "total_duration": total_duration,
        }
