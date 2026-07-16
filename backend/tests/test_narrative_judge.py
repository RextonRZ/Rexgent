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
async def test_low_dialogue_density_blocks():
    judge = NarrativeJudge.__new__(NarrativeJudge)
    judge.qwen = MagicMock()
    judge.qwen.chat_json = AsyncMock(return_value={
        "scores": {"tension_arc": 8.0, "character_consistency": 8.0, "pacing": 8.0,
                   "dialogue_naturalness": 8.0, "genre_adherence": 8.0, "dialogue_density": 2.0},
        "overall": 7.0,
        "blocking_issues": [],
        "top_strengths": [],
        "top_weaknesses": ["Too visual, barely any spoken dialogue"],
        "recommendation": "PROCEED",
    })
    judge.prompt_template = "placeholder"

    result = await judge.evaluate(script_json={"scenes": []}, blocking_threshold=5.0)
    assert any("dialogue_density" in b for b in result["blocking_issues"])
    assert result["recommendation"] == "REVISE_FIRST"


@pytest.mark.asyncio
async def test_budgeted_dialogue_density_does_not_block():
    # the 30s bug: the dialogue BUDGET caps a script at ~5 short lines, and the
    # judge scored density 4.0 -> auto-blocked -> a rewrite loop that made the
    # script worse. Density is a format preference: only near-silent (<3)
    # blocks; 4.0 must NOT.
    judge = NarrativeJudge.__new__(NarrativeJudge)
    judge.qwen = MagicMock()
    judge.qwen.chat_json = AsyncMock(return_value={
        "scores": {"tension_arc": 7.0, "character_consistency": 7.5, "pacing": 6.5,
                   "dialogue_naturalness": 6.5, "genre_adherence": 8.0, "dialogue_density": 4.0},
        "overall": 6.5,
        "blocking_issues": [],
        "top_strengths": [],
        "top_weaknesses": [],
        "recommendation": "PROCEED",
    })
    judge.prompt_template = "placeholder"

    result = await judge.evaluate(script_json={"scenes": []}, blocking_threshold=5.0)
    assert result["blocking_issues"] == []
    assert result["recommendation"] == "PROCEED"


@pytest.mark.asyncio
async def test_judge_receives_format_context():
    # the judge must know the target length + line budget, or it judges a
    # 30-second piece as if length were free
    judge = NarrativeJudge.__new__(NarrativeJudge)
    judge.qwen = MagicMock()
    judge.qwen.chat_json = AsyncMock(return_value={
        "scores": {}, "overall": 7.0, "blocking_issues": [],
        "top_strengths": [], "top_weaknesses": [], "recommendation": "PROCEED",
    })
    judge.prompt_template = "placeholder"

    await judge.evaluate(script_json={"scenes": []}, target_length=30)
    sent = judge.qwen.chat_json.call_args.kwargs["messages"][1]["content"]
    assert "30" in sent
    assert "5" in sent          # the line budget for 30s
    assert "FORMAT CONTEXT" in sent


@pytest.mark.asyncio
async def test_judge_handles_non_dict_response():
    judge = NarrativeJudge.__new__(NarrativeJudge)
    judge.qwen = MagicMock()
    judge.qwen.chat_json = AsyncMock(return_value=["bad"])
    judge.prompt_template = "placeholder"

    result = await judge.evaluate(script_json={"scenes": []})
    assert result["recommendation"] == "MAJOR_REWRITE"
    assert result["scores"] == {}
