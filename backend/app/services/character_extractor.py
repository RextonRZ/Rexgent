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


# A zh run answers the schema in Chinese; every downstream check compares
# against the English enums (the voice pool splits on "female", role ordering
# uppercases). Map the common Chinese answers back onto the schema's values.
_GENDER_VALUES = {
    "male": "male", "female": "female",
    "男": "male", "男性": "male", "男生": "male",
    "女": "female", "女性": "female", "女生": "female",
}
_ROLE_VALUES = {
    "protagonist": "PROTAGONIST", "antagonist": "ANTAGONIST",
    "supporting": "SUPPORTING", "minor": "MINOR",
    "主角": "PROTAGONIST", "主人公": "PROTAGONIST",
    "反派": "ANTAGONIST", "反面角色": "ANTAGONIST", "对手": "ANTAGONIST",
    "配角": "SUPPORTING", "支持角色": "SUPPORTING",
    "次要": "MINOR", "次要角色": "MINOR", "龙套": "MINOR",
}


def normalize_extracted(characters: list) -> list:
    """Normalize gender/role onto the schema's English enum values in place;
    values the maps don't know stay untouched."""
    for c in characters or []:
        if not isinstance(c, dict):
            continue
        g = str(c.get("gender") or "").strip().lower()
        if g in _GENDER_VALUES:
            c["gender"] = _GENDER_VALUES[g]
        r = str(c.get("role") or "").strip().lower()
        if r in _ROLE_VALUES:
            c["role"] = _ROLE_VALUES[r]
    return characters


class CharacterExtractor:
    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("character_extract.txt")

    async def extract(self, script_json: dict, language: str = "en") -> list[dict]:
        system = self.prompt_template + language_instruction(language)
        if language == "zh":
            # prose in Chinese, but the enum fields must stay machine-readable
            system += ("\nEXCEPTION: the values of `role`, `gender` and "
                       "`speech_pattern` must stay EXACTLY the English options "
                       "the schema lists (e.g. PROTAGONIST, female, casual). "
                       "`gender` is REQUIRED and never null: read the script's "
                       "pronouns (她 = female, 他 = male) and the character's "
                       "relationships (哥哥/弟弟 = male, 姐姐/妹妹 = female); "
                       "commit to the most plausible reading.")
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(script_json, ensure_ascii=False)},
        ]
        result = await self.qwen.chat_json(messages=messages, temperature=0.2, task="characters")
        # JSON mode may wrap the array in an object — unwrap it
        characters = normalize_extracted(QwenClient.as_list(result))
        # gender drives voice matching and plate prompts downstream — a null
        # slips a male character into the female-first voice pool, so backstop
        # the prompt's REQUIRED rule with the honorific heuristic
        for c in characters:
            if isinstance(c, dict) and not (c.get("gender") or "").strip():
                inferred = _gender_from_name(str(c.get("name") or ""))
                if inferred:
                    c["gender"] = inferred
        return characters
