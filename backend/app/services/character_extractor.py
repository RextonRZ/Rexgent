import json
from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.services.language import language_instruction
from app.config import get_settings

_MALE_HONORIFICS = ("MR.", "MR ", "SIR ", "LORD ", "KING ", "PRINCE ", "FATHER ", "UNCLE ")
_FEMALE_HONORIFICS = ("MRS.", "MRS ", "MS.", "MS ", "MISS ", "MADAM", "LADY ",
                      "QUEEN ", "PRINCESS ", "MOTHER ", "AUNT ")


def _gender_from_name(name: str) -> str | None:
    """Deterministic fallback for a model that still returned no gender —
    honorifics in the character's own name settle it (MR. ROARKE once got a
    female voice because his gender came back null)."""
    upper = (name or "").upper().strip()
    if upper.startswith(_MALE_HONORIFICS):
        return "male"
    if upper.startswith(_FEMALE_HONORIFICS):
        return "female"
    return None


class CharacterExtractor:
    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("character_extract.txt")

    async def extract(self, script_json: dict, language: str = "en") -> list[dict]:
        messages = [
            {"role": "system", "content": self.prompt_template + language_instruction(language)},
            {"role": "user", "content": json.dumps(script_json, ensure_ascii=False)},
        ]
        result = await self.qwen.chat_json(messages=messages, temperature=0.2, task="characters")
        # JSON mode may wrap the array in an object — unwrap it
        characters = QwenClient.as_list(result)
        # gender drives voice matching and plate prompts downstream — a null
        # slips a male character into the female-first voice pool, so backstop
        # the prompt's REQUIRED rule with the honorific heuristic
        for c in characters:
            if isinstance(c, dict) and not (c.get("gender") or "").strip():
                inferred = _gender_from_name(str(c.get("name") or ""))
                if inferred:
                    c["gender"] = inferred
        return characters
