import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.script_structurer import ScriptStructurer


@pytest.mark.asyncio
async def test_structure_script_returns_valid_json():
    mock_response = {
        "title": "The Last Signal",
        "genre": "sci-fi thriller",
        "logline": "A detective discovers her partner is AI.",
        "acts": [{"act_number": 1, "summary": "Setup"}],
        "scenes": [{
            "scene_number": 1,
            "act_number": 1,
            "heading": "INT. OFFICE - DAY",
            "location": "Police office",
            "time_of_day": "DAY",
            "summary": "Yuki reviews case files.",
            "characters_present": ["YUKI"],
            "dialogue_lines": [],
            "stage_directions": ["YUKI sits at desk"],
            "emotional_beat": "tension"
        }],
        "characters_mentioned": ["YUKI"]
    }

    structurer = ScriptStructurer.__new__(ScriptStructurer)
    structurer.qwen = MagicMock()
    structurer.qwen.chat_json = AsyncMock(return_value=mock_response)
    structurer.system_prompt = "test prompt"

    result = await structurer.structure(raw_text="INT. OFFICE - DAY\nYUKI sits at desk.")
    assert result["title"] == "The Last Signal"
    assert len(result["scenes"]) == 1
    assert result["scenes"][0]["characters_present"] == ["YUKI"]


def test_prompt_forbids_splitting_continuous_moments():
    from app.services.prompt_loader import load_prompt
    t = load_prompt("script_structure.txt")
    assert "SAME location" in t
    assert "ONE scene" in t
