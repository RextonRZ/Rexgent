"""The vertical micro-drama format rules live in the prompts; these tests pin
them so a prompt edit can't silently drop the hook/cliffhanger conventions
the judge enforces."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.prompt_loader import load_prompt
from app.mcp_tools.narrative_judge import NarrativeJudge


def test_script_prompt_demands_hook_and_cliffhanger():
    prompt = load_prompt("script_generate.txt")
    assert "THE HOOK" in prompt
    assert "first 3 seconds" in prompt.lower() or "first 3 seconds" in prompt
    assert "CLIFFHANGER EVERY EPISODE" in prompt
    assert "PACING" in prompt
    # anti-patterns are named so the model can't default to them
    assert "waking up" in prompt


def test_storyboard_prompt_stages_the_hook():
    prompt = load_prompt("storyboard_generate.txt")
    assert "THE HOOK" in prompt
    assert "SCENE 1" in prompt
    # the hook must stage what is written, not invent content
    assert "do not invent new content for the hook" in prompt


def test_judge_prompt_scores_format_axes():
    prompt = load_prompt("narrative_judge.txt")
    assert "hook_strength" in prompt
    assert "cliffhanger_pull" in prompt
    assert "8 axes" in prompt


@pytest.mark.asyncio
async def test_weak_hook_blocks_and_demands_revision():
    judge = NarrativeJudge.__new__(NarrativeJudge)
    judge.qwen = MagicMock()
    judge.prompt_template = "placeholder"
    judge.qwen.chat_json = AsyncMock(return_value={
        "scores": {"tension_arc": 8, "hook_strength": 3, "cliffhanger_pull": 7},
        "overall": 7.0,
        "blocking_issues": [],
    })
    result = await judge.evaluate({"scenes": []})
    assert result["recommendation"] == "REVISE_FIRST"
    assert any("hook_strength" in issue for issue in result["blocking_issues"])
