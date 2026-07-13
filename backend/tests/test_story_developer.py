import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.story_developer import StoryDeveloper

TREATMENT = {
    "logline": "A goalkeeper must save the penalty of the brother who ended his career.",
    "central_conflict": "Two estranged brothers on opposite sides of the deciding kick.",
    "key_relationship": {"between": "Eirik and Jonas", "tension": "a career-ending tackle they never spoke about"},
    "the_secret": "Jonas let Eirik believe the injury was an accident.",
    "stakes": "the last chance to be brothers again, not just the match",
    "the_turn": "Jonas reveals he knew it was deliberate all along",
    "why_now": "the final whistle forces a reckoning they have dodged for years",
    "cast": ["Eirik — the striker seeking redemption", "Jonas — the keeper hiding a grudge"],
}


@pytest.mark.asyncio
async def test_develop_returns_treatment():
    dev = StoryDeveloper.__new__(StoryDeveloper)
    dev.qwen = MagicMock()
    dev.qwen.chat_json = AsyncMock(return_value=TREATMENT)
    dev.prompt_template = "{premise}{genre}{tone}{episode_count}"
    out = await dev.develop("a footballer takes a penalty", "sports", "tense", 1)
    assert out["logline"].startswith("A goalkeeper")


@pytest.mark.asyncio
async def test_develop_degrades_to_empty_on_failure():
    """Development is enrichment, never a gate — a flaky call must not block
    the drama, so the screenwriter still writes from the bare premise."""
    dev = StoryDeveloper.__new__(StoryDeveloper)
    dev.qwen = MagicMock()
    dev.qwen.chat_json = AsyncMock(side_effect=RuntimeError("model down"))
    dev.prompt_template = "{premise}{genre}{tone}{episode_count}"
    assert await dev.develop("x", "drama", "dark", 1) == {}


@pytest.mark.asyncio
async def test_develop_rejects_shapeless_output():
    dev = StoryDeveloper.__new__(StoryDeveloper)
    dev.qwen = MagicMock()
    dev.qwen.chat_json = AsyncMock(return_value=["not", "a", "dict"])
    dev.prompt_template = "{premise}{genre}{tone}{episode_count}"
    assert await dev.develop("x", "drama", "dark", 1) == {}


def test_as_brief_folds_the_spine_into_prompt_text():
    brief = StoryDeveloper.as_brief(TREATMENT)
    assert "Logline:" in brief
    assert "The mid-story turn" in brief
    assert "Eirik and Jonas" in brief
    # an empty treatment yields empty text so the prompt reads "None"
    assert StoryDeveloper.as_brief({}) == ""


def test_headline_surfaces_the_turn_for_the_crew_node():
    assert "reveals" in StoryDeveloper.headline(TREATMENT)
    assert StoryDeveloper.headline({}) == "wrote from the premise as-is"
