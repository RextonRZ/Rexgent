"""Official Qwen-TTS voices (available on qwen3-tts-flash). Single source of truth
for the preset picker and gender-aware default assignment.

https://www.alibabacloud.com/help/en/model-studio/qwen-tts-voice-list
Multi-word voice names (Eldric Sage, Ono Anna, Radio Gol) are omitted since their
exact API `voice` value is ambiguous.
"""

# id == the value passed to the TTS `voice` parameter.
VOICES: list[dict] = [
    # ── Female ──────────────────────────────────────────────────────────
    {"id": "Cherry", "gender": "female", "desc": "Sunny, friendly young woman"},
    {"id": "Serena", "gender": "female", "desc": "Gentle young woman"},
    {"id": "Chelsie", "gender": "female", "desc": "Soft, virtual-girlfriend tone"},
    {"id": "Momo", "gender": "female", "desc": "Playful and cheerful"},
    {"id": "Vivian", "gender": "female", "desc": "Confident, cute, slightly feisty"},
    {"id": "Maia", "gender": "female", "desc": "Intellect blended with gentleness"},
    {"id": "Bella", "gender": "female", "desc": "Bubbly, mischievous"},
    {"id": "Jennifer", "gender": "female", "desc": "Cinematic American-English"},
    {"id": "Katerina", "gender": "female", "desc": "Mature woman, rich rhythm"},
    {"id": "Mia", "gender": "female", "desc": "Gentle, soft, obedient"},
    {"id": "Bellona", "gender": "female", "desc": "Powerful, stirring, dramatic"},
    {"id": "Bunny", "gender": "female", "desc": "Cute little girl"},
    {"id": "Elias", "gender": "female", "desc": "Academic, storytelling"},
    {"id": "Nini", "gender": "female", "desc": "Soft, clingy, sweet"},
    {"id": "Seren", "gender": "female", "desc": "Gentle, soothing (sleep)"},
    {"id": "Stella", "gender": "female", "desc": "Enthusiastic, dramatic"},
    {"id": "Sonrisa", "gender": "female", "desc": "Cheerful Latin-American woman"},
    {"id": "Sohee", "gender": "female", "desc": "Warm, expressive Korean"},
    {"id": "Jada", "gender": "female", "desc": "Energetic (Shanghainese)"},
    {"id": "Sunny", "gender": "female", "desc": "Sweet Sichuan girl (Sichuan)"},
    {"id": "Kiki", "gender": "female", "desc": "Sweet Hong Kong girl (Cantonese)"},
    # ── Male ────────────────────────────────────────────────────────────
    {"id": "Ethan", "gender": "male", "desc": "Sunny, warm, energetic"},
    {"id": "Moon", "gender": "male", "desc": "Bold and handsome"},
    {"id": "Kai", "gender": "male", "desc": "Soothing, spa-like"},
    {"id": "Nofish", "gender": "male", "desc": "Designer, no retroflex sounds"},
    {"id": "Ryan", "gender": "male", "desc": "Rhythmic, dramatic flair"},
    {"id": "Aiden", "gender": "male", "desc": "American-English young man"},
    {"id": "Mochi", "gender": "male", "desc": "Clever, quick-witted young adult"},
    {"id": "Vincent", "gender": "male", "desc": "Raspy, smoky, heroic"},
    {"id": "Neil", "gender": "male", "desc": "Professional news anchor"},
    {"id": "Arthur", "gender": "male", "desc": "Earthy, unhurried storyteller"},
    {"id": "Pip", "gender": "male", "desc": "Playful, mischievous boy"},
    {"id": "Bodega", "gender": "male", "desc": "Passionate Spanish man"},
    {"id": "Alek", "gender": "male", "desc": "Cold yet warm (Russian)"},
    {"id": "Dolce", "gender": "male", "desc": "Laid-back Italian man"},
    {"id": "Lenn", "gender": "male", "desc": "German youth, post-punk"},
    {"id": "Emilien", "gender": "male", "desc": "Romantic French"},
    {"id": "Andre", "gender": "male", "desc": "Magnetic, natural, steady"},
    {"id": "Dylan", "gender": "male", "desc": "Beijing hutong young man (Beijing)"},
    {"id": "Li", "gender": "male", "desc": "Patient yoga teacher (Nanjing)"},
    {"id": "Marcus", "gender": "male", "desc": "Deep voice (Shaanxi)"},
    {"id": "Roy", "gender": "male", "desc": "Lively Taiwanese (Southern Min)"},
    {"id": "Peter", "gender": "male", "desc": "Tianjin crosstalk (Tianjin)"},
    {"id": "Eric", "gender": "male", "desc": "Chengdu man (Sichuan)"},
    {"id": "Rocky", "gender": "male", "desc": "Humorous, witty (Cantonese)"},
]

ALL_IDS = {v["id"] for v in VOICES}

# Clean, general-purpose voices used for automatic assignment (dialect/novelty
# voices stay available in the picker but aren't auto-assigned).
FEMALE_DEFAULTS = ["Cherry", "Serena", "Chelsie", "Jennifer", "Katerina", "Maia", "Bella", "Stella"]
MALE_DEFAULTS = ["Ethan", "Ryan", "Aiden", "Andre", "Moon", "Neil", "Kai", "Vincent"]


def gender_bucket(gender: str | None) -> str | None:
    g = str(gender or "").lower()
    if any(w in g for w in ("female", "woman", "girl", "lady")):
        return "female"
    if any(w in g for w in ("male", "man", "boy", "guy")):
        return "male"
    return None


def default_voice(gender: str | None, index: int = 0) -> str:
    """Pick a gender-appropriate preset, rotating by index so multiple
    same-gender characters get distinct voices."""
    bucket = gender_bucket(gender)
    pool = (FEMALE_DEFAULTS if bucket == "female"
            else MALE_DEFAULTS if bucket == "male"
            else FEMALE_DEFAULTS + MALE_DEFAULTS)
    return pool[index % len(pool)]
