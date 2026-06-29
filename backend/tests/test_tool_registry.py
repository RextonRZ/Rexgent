import pytest
from unittest.mock import AsyncMock, patch
from app.mcp_tools.registry import TOOL_DEFINITIONS, get_tool


def test_six_tools_registered():
    names = {t["name"] for t in TOOL_DEFINITIONS}
    assert names == {
        "scene_prompt_craft", "consistency_guard", "token_optimizer",
        "narrative_judge", "plot_gap_detector", "ending_engine",
    }


def test_definitions_have_schemas():
    for t in TOOL_DEFINITIONS:
        assert "inputSchema" in t and t["inputSchema"]["type"] == "object"


def test_get_tool_returns_callable():
    assert callable(get_tool("plot_gap_detector"))


def test_token_tool_runs_sync():
    # token_optimizer is pure — exercise the registry call path.
    result = get_tool("token_optimizer")({"shots": [], "budget_usd": 40.0})
    assert result["total_shots"] == 0


@pytest.mark.asyncio
async def test_plot_gap_tool_delegates():
    with patch("app.mcp_tools.registry.PlotGapDetector") as P:
        P.return_value.detect = AsyncMock(return_value={"total_flags": 0, "flags": []})
        result = await get_tool("plot_gap_detector")({"script": {"scenes": []}})
        assert result["total_flags"] == 0
