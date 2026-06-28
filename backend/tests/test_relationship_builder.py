import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.relationship_builder import RelationshipBuilder


@pytest.mark.asyncio
async def test_extract_returns_relationships():
    builder = RelationshipBuilder.__new__(RelationshipBuilder)
    builder.qwen = MagicMock()
    builder.qwen.chat_json = AsyncMock(return_value=[
        {
            "from_character": "YUKI",
            "to_character": "ARIA",
            "relationship_type": "ALLY",
            "strength": 7,
            "description": "Detective and her AI partner",
            "first_established_scene": 1,
            "evidence_quote": "We work together.",
            "evolution": "DETERIORATES",
            "evolution_description": "Trust erodes as Yuki suspects ARIA",
        }
    ])
    builder.prompt_template = "placeholder"

    result = await builder.extract(script_json={"scenes": []}, characters_json=[{"name": "YUKI"}, {"name": "ARIA"}])
    assert len(result) == 1
    assert result[0]["relationship_type"] == "ALLY"
    assert result[0]["evolution"] == "DETERIORATES"


@pytest.mark.asyncio
async def test_extract_handles_non_list():
    builder = RelationshipBuilder.__new__(RelationshipBuilder)
    builder.qwen = MagicMock()
    builder.qwen.chat_json = AsyncMock(return_value={"not": "list"})
    builder.prompt_template = "placeholder"

    result = await builder.extract(script_json={}, characters_json=[])
    assert result == []
