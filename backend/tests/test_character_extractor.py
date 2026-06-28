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
