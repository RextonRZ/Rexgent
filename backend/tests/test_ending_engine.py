import pytest
from unittest.mock import AsyncMock, MagicMock
from app.mcp_tools.ending_engine import EndingEngine


@pytest.mark.asyncio
async def test_analyse_returns_complete():
    engine = EndingEngine.__new__(EndingEngine)
    engine.qwen = MagicMock()
    engine.qwen.chat_json = AsyncMock(return_value={
        "has_ending": True,
        "ending_quality": "COMPLETE",
        "main_conflict_resolved": True,
        "protagonist_arc_complete": True,
        "open_threads": [],
        "assessment": "Story has a satisfying ending.",
        "alternative_endings": [],
    })
    engine.prompt_template = "placeholder"

    result = await engine.analyse(script_json={"scenes": []})
    assert result["has_complete_ending"] is True
    assert result["ending_quality"] == "COMPLETE"
    assert result["analysis"]["main_conflict_resolved"] is True
    assert result["alternatives"] == []


@pytest.mark.asyncio
async def test_analyse_returns_alternatives_when_incomplete():
    engine = EndingEngine.__new__(EndingEngine)
    engine.qwen = MagicMock()
    engine.qwen.chat_json = AsyncMock(return_value={
        "has_ending": False,
        "ending_quality": "PARTIAL",
        "main_conflict_resolved": False,
        "protagonist_arc_complete": True,
        "open_threads": ["AI origin unexplained"],
        "assessment": "Ending is incomplete.",
        "alternative_endings": [
            {"id": "ending_a", "title": "The sacrifice", "summary": "AI sacrifices itself", "emotional_tone": "BITTERSWEET", "compatibility_score": 9.2},
            {"id": "ending_b", "title": "The reveal", "summary": "Yuki is also AI", "emotional_tone": "AMBIGUOUS", "compatibility_score": 7.1},
            {"id": "ending_c", "title": "The compromise", "summary": "They let each other go", "emotional_tone": "HOPEFUL", "compatibility_score": 8.8},
        ],
    })
    engine.prompt_template = "placeholder"

    result = await engine.analyse(script_json={"scenes": []})
    assert result["has_complete_ending"] is False
    assert result["ending_quality"] == "PARTIAL"
    assert len(result["alternatives"]) == 3
    assert result["analysis"]["open_threads"] == ["AI origin unexplained"]


@pytest.mark.asyncio
async def test_analyse_handles_non_dict_response():
    engine = EndingEngine.__new__(EndingEngine)
    engine.qwen = MagicMock()
    engine.qwen.chat_json = AsyncMock(return_value=["unexpected", "list"])
    engine.prompt_template = "placeholder"

    result = await engine.analyse(script_json={"scenes": []})
    assert result["has_complete_ending"] is False
    assert result["ending_quality"] == "MISSING"
    assert result["alternatives"] == []
