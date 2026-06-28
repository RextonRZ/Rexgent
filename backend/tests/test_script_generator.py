import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.script_generator import ScriptGenerator


@pytest.mark.asyncio
async def test_generate_returns_raw_text():
    generator = ScriptGenerator.__new__(ScriptGenerator)
    generator.qwen = MagicMock()
    generator.qwen.chat = AsyncMock(return_value="INT. OFFICE - DAY\n\nYUKI enters the room.\n\nYUKI\nSomething feels wrong.")
    generator.prompt_template = "Genre: {genre}\nPremise: {premise}\nTone: {tone}\nNumber of episodes: {episode_count}\nTarget length per episode: {target_length} minutes\nAdditional notes: {notes}"

    result = await generator.generate(
        genre="sci-fi thriller",
        premise="A detective discovers her partner is AI",
        tone="dark",
        episode_count=1,
        target_length=5,
    )
    assert "INT. OFFICE" in result
    assert "YUKI" in result


@pytest.mark.asyncio
async def test_generate_passes_all_params():
    generator = ScriptGenerator.__new__(ScriptGenerator)
    generator.qwen = MagicMock()
    generator.qwen.chat = AsyncMock(return_value="script text")
    generator.prompt_template = "Genre: {genre}\nPremise: {premise}\nTone: {tone}\nNumber of episodes: {episode_count}\nTarget length per episode: {target_length} minutes\nAdditional notes: {notes}"

    await generator.generate(
        genre="horror",
        premise="Haunted house",
        tone="creepy",
        episode_count=2,
        target_length=10,
        notes="Include a twist",
    )

    call_args = generator.qwen.chat.call_args
    prompt = call_args[1]["messages"][0]["content"]
    assert "horror" in prompt
    assert "Haunted house" in prompt
    assert "Include a twist" in prompt
