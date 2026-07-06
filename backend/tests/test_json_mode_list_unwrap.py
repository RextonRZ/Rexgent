"""Regression: native JSON mode (response_format json_object) makes the model
return an OBJECT, so callers that expect a bare array got {} -> [] and
silently produced nothing (first seen as relationship graphs with no edges).
Every list-expecting caller must unwrap the wrapped shape."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.qwen_client import QwenClient
from app.services.relationship_builder import RelationshipBuilder
from app.services.character_extractor import CharacterExtractor
from app.services.storyboard_generator import StoryboardGenerator


REL = {"from_character": "YUKI", "to_character": "ARIA",
       "relationship_type": "RIVAL", "strength": 7}


def test_as_list_passes_lists_through():
    assert QwenClient.as_list([1, 2]) == [1, 2]


def test_as_list_unwraps_single_key_object():
    assert QwenClient.as_list({"relationships": [REL]}) == [REL]
    assert QwenClient.as_list({"shots": [{"shot_number": 1}]}) == [{"shot_number": 1}]


def test_as_list_garbage_is_empty():
    assert QwenClient.as_list("nope") == []
    assert QwenClient.as_list({"count": 3}) == []
    assert QwenClient.as_list(None) == []


@pytest.mark.asyncio
async def test_relationships_survive_json_mode_wrapping():
    rb = RelationshipBuilder.__new__(RelationshipBuilder)
    rb.qwen = MagicMock()
    rb.qwen.chat_json = AsyncMock(return_value={"relationships": [REL]})
    rb.prompt_template = "placeholder"
    out = await rb.extract({"scenes": []}, [])
    assert out == [REL]


@pytest.mark.asyncio
async def test_characters_survive_json_mode_wrapping():
    ce = CharacterExtractor.__new__(CharacterExtractor)
    ce.qwen = MagicMock()
    ce.qwen.chat_json = AsyncMock(return_value={"characters": [{"name": "YUKI"}]})
    ce.prompt_template = "placeholder"
    out = await ce.extract({"scenes": []})
    assert out == [{"name": "YUKI"}]


@pytest.mark.asyncio
async def test_storyboard_shots_survive_json_mode_wrapping():
    gen = StoryboardGenerator.__new__(StoryboardGenerator)
    gen.qwen = MagicMock()
    gen.qwen.chat_json = AsyncMock(return_value={
        "shots": [{"shot_number": 1, "dialogue": "Run."}]})
    gen.prompt_template = "placeholder"
    shots = await gen.generate_for_scene({"dialogue": ["Run."]}, [])
    assert shots[0]["shot_number"] == 1
