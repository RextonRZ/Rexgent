import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.character_extractor import CharacterExtractor


@pytest.mark.asyncio
async def test_extract_returns_characters():
    extractor = CharacterExtractor.__new__(CharacterExtractor)
    extractor.qwen = MagicMock()
    extractor.qwen.chat_json = AsyncMock(return_value=[
        {
            "name": "YUKI",
            "role": "PROTAGONIST",
            "first_appearance_scene": 1,
            "gender": "female",
            "estimated_age": "late 30s",
            "physical_description": "sharp features, short black hair",
            "personality_summary": "Guarded detective with trust issues.",
            "key_dialogue_samples": ["I don't trust machines."],
            "speech_pattern": "terse",
            "emotional_arc": {"start": "guarded", "midpoint": "conflicted", "end": "accepting"},
            "relationships": ["partner to ARIA"],
        }
    ])
    extractor.prompt_template = "placeholder"

    result = await extractor.extract(script_json={"scenes": []})
    assert len(result) == 1
    assert result[0]["name"] == "YUKI"
    assert result[0]["role"] == "PROTAGONIST"


@pytest.mark.asyncio
async def test_extract_handles_non_list():
    extractor = CharacterExtractor.__new__(CharacterExtractor)
    extractor.qwen = MagicMock()
    extractor.qwen.chat_json = AsyncMock(return_value={"not": "a list"})
    extractor.prompt_template = "placeholder"

    result = await extractor.extract(script_json={"scenes": []})
    assert result == []


@pytest.mark.asyncio
async def test_missing_gender_falls_back_to_honorifics():
    # the model returned gender null for half the cast once — MR. ROARKE got a
    # female voice. Honorifics in the name settle it deterministically.
    extractor = CharacterExtractor.__new__(CharacterExtractor)
    extractor.qwen = MagicMock()
    extractor.qwen.chat_json = AsyncMock(return_value=[
        {"name": "MR. ROARKE", "gender": None},
        {"name": "MRS. COLE", "gender": ""},
        {"name": "KAITO", "gender": None},        # no honorific -> left as-is
        {"name": "LADY WHISTLE", "gender": None},
        {"name": "GWEN", "gender": "female"},     # explicit stays untouched
    ])
    extractor.prompt_template = "placeholder"

    out = await extractor.extract(script_json={"scenes": []})
    by = {c["name"]: c.get("gender") for c in out}
    assert by["MR. ROARKE"] == "male"
    assert by["MRS. COLE"] == "female"
    assert by["LADY WHISTLE"] == "female"
    assert by["KAITO"] is None
    assert by["GWEN"] == "female"


def test_normalize_extracted_maps_chinese_enum_values():
    # a zh run answers the schema in Chinese; downstream checks compare
    # against the English enums (voice pick by gender, role ordering)
    from app.services.character_extractor import normalize_extracted
    data = [{"name": "小雨", "gender": "女", "role": "主角"},
            {"name": "大明", "gender": "男性", "role": "配角"},
            {"name": "Anna", "gender": "female", "role": "protagonist"}]
    out = normalize_extracted(data)
    assert out[0]["gender"] == "female" and out[0]["role"] == "PROTAGONIST"
    assert out[1]["gender"] == "male" and out[1]["role"] == "SUPPORTING"
    assert out[2]["gender"] == "female" and out[2]["role"] == "PROTAGONIST"


def test_normalize_extracted_leaves_unknown_values_alone():
    from app.services.character_extractor import normalize_extracted
    data = [{"name": "X", "gender": None, "role": "ANTAGONIST"}]
    out = normalize_extracted(data)
    assert out[0]["gender"] is None
    assert out[0]["role"] == "ANTAGONIST"
