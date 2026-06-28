import pytest
from unittest.mock import AsyncMock, MagicMock
from app.mcp_tools.narrative_judge import NarrativeJudge


@pytest.mark.asyncio
async def test_judge_returns_proceed():
    judge = NarrativeJudge.__new__(NarrativeJudge)
    judge.qwen = MagicMock()
    judge.qwen.chat_json = AsyncMock(return_value={
        "scores": {"tension_arc": 7.5, "character_consistency": 8.0, "pacing": 6.5, "dialogue_naturalness": 7.0, "genre_adherence": 8.5},
        "overall": 7.5,
        "blocking_issues": [],
        "top_strengths": ["Strong atmosphere"],
        "top_weaknesses": ["Scene 4 pacing drags"],
        "recommendation": "PROCEED",
    })
    judge.prompt_template = "placeholder"

    result = await judge.evaluate(script_json={"scenes": []})
    assert result["recommendation"] == "PROCEED"
    assert result["scores"]["tension_arc"] == 7.5
    assert len(result["blocking_issues"]) == 0


@pytest.mark.asyncio
async def test_judge_blocks_below_threshold():
    judge = NarrativeJudge.__new__(NarrativeJudge)
    judge.qwen = MagicMock()
    judge.qwen.chat_json = AsyncMock(return_value={
        "scores": {"tension_arc": 3.0, "character_consistency": 8.0, "pacing": 6.5, "dialogue_naturalness": 7.0, "genre_adherence": 8.5},
        "overall": 6.6,
        "blocking_issues": [],
        "top_strengths": [],
        "top_weaknesses": ["No tension"],
        "recommendation": "PROCEED",
    })
    judge.prompt_template = "placeholder"

    result = await judge.evaluate(script_json={"scenes": []}, blocking_threshold=5.0)
    assert result["recommendation"] == "REVISE_FIRST"
    assert len(result["blocking_issues"]) >= 1


@pytest.mark.asyncio
async def test_judge_major_rewrite_when_low_overall():
    judge = NarrativeJudge.__new__(NarrativeJudge)
    judge.qwen = MagicMock()
    judge.qwen.chat_json = AsyncMock(return_value={
        "scores": {"tension_arc": 5.5, "character_consistency": 5.5, "pacing": 5.5, "dialogue_naturalness": 5.5, "genre_adherence": 5.5},
        "overall": 5.5,
        "blocking_issues": [],
        "top_strengths": [],
        "top_weaknesses": [],
        "recommendation": "PROCEED",
    })
    judge.prompt_template = "placeholder"

    result = await judge.evaluate(script_json={"scenes": []})
    assert result["recommendation"] == "MAJOR_REWRITE"


@pytest.mark.asyncio
async def test_judge_handles_non_dict_response():
    judge = NarrativeJudge.__new__(NarrativeJudge)
    judge.qwen = MagicMock()
    judge.qwen.chat_json = AsyncMock(return_value=["bad"])
    judge.prompt_template = "placeholder"

    result = await judge.evaluate(script_json={"scenes": []})
    assert result["recommendation"] == "MAJOR_REWRITE"
    assert result["scores"] == {}
