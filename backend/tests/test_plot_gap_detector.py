import pytest
from unittest.mock import AsyncMock, MagicMock
from app.mcp_tools.plot_gap_detector import PlotGapDetector


@pytest.mark.asyncio
async def test_detect_returns_flags():
    detector = PlotGapDetector.__new__(PlotGapDetector)
    detector.qwen = MagicMock()
    detector.qwen.chat_json = AsyncMock(return_value=[
        {
            "flag_type": "MISSING_MOTIVATION",
            "severity": "MAJOR",
            "scene_number": 3,
            "description": "Yuki shoots the drone without reason",
            "evidence": "Scene 3, line 12",
            "suggestion": "Add earlier suspicion scene",
        }
    ])
    detector.prompt_template = "placeholder"

    result = await detector.detect(script_json={"scenes": []}, sensitivity="NORMAL")
    assert result["total_flags"] == 1
    assert result["major_count"] == 1
    assert result["flags"][0]["flag_type"] == "MISSING_MOTIVATION"
    assert result["flags"][0]["status"] == "OPEN"
    assert result["flags"][0]["flag_id"].startswith("flag_")


@pytest.mark.asyncio
async def test_detect_empty_returns_zero():
    detector = PlotGapDetector.__new__(PlotGapDetector)
    detector.qwen = MagicMock()
    detector.qwen.chat_json = AsyncMock(return_value=[])
    detector.prompt_template = "placeholder"

    result = await detector.detect(script_json={"scenes": []}, sensitivity="NORMAL")
    assert result["total_flags"] == 0
    assert result["flags"] == []


@pytest.mark.asyncio
async def test_detect_handles_non_list_response():
    detector = PlotGapDetector.__new__(PlotGapDetector)
    detector.qwen = MagicMock()
    detector.qwen.chat_json = AsyncMock(return_value={"unexpected": "object"})
    detector.prompt_template = "placeholder"

    result = await detector.detect(script_json={"scenes": []})
    assert result["total_flags"] == 0


@pytest.mark.asyncio
async def test_detect_counts_severities():
    detector = PlotGapDetector.__new__(PlotGapDetector)
    detector.qwen = MagicMock()
    detector.qwen.chat_json = AsyncMock(return_value=[
        {"flag_type": "PACING_ISSUE", "severity": "CRITICAL", "scene_number": 1, "description": "x", "evidence": "y", "suggestion": "z"},
        {"flag_type": "PACING_ISSUE", "severity": "MAJOR", "scene_number": 2, "description": "x", "evidence": "y", "suggestion": "z"},
        {"flag_type": "PACING_ISSUE", "severity": "MINOR", "scene_number": 3, "description": "x", "evidence": "y", "suggestion": "z"},
    ])
    detector.prompt_template = "placeholder"

    result = await detector.detect(script_json={"scenes": []})
    assert result["total_flags"] == 3
    assert result["critical_count"] == 1
    assert result["major_count"] == 1
    assert result["minor_count"] == 1
