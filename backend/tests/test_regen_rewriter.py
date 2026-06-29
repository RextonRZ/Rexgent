import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.regen_prompt_rewriter import RegenPromptRewriter


@pytest.mark.asyncio
async def test_rewrite_returns_revised_prompt():
    rewriter = RegenPromptRewriter.__new__(RegenPromptRewriter)
    rewriter.qwen = MagicMock()
    rewriter.qwen.chat_json = AsyncMock(return_value={
        "revised_prompt": "Close-up, softer warm lighting, young woman with sharp cheekbones, 5s",
        "changes_made": ["softened lighting per feedback"],
        "confidence": 88,
    })
    rewriter.prompt_template = "placeholder"

    result = await rewriter.rewrite(
        original_prompt="Close-up, harsh lighting, young woman with sharp cheekbones, 5s",
        flag_description="lighting too bright",
        flag_type="LIGHTING",
    )
    assert "softer" in result["revised_prompt"]
    assert result["confidence"] == 88


@pytest.mark.asyncio
async def test_rewrite_falls_back_on_bad_response():
    rewriter = RegenPromptRewriter.__new__(RegenPromptRewriter)
    rewriter.qwen = MagicMock()
    rewriter.qwen.chat_json = AsyncMock(return_value=["bad"])
    rewriter.prompt_template = "placeholder"

    result = await rewriter.rewrite(
        original_prompt="original", flag_description="x", flag_type="OTHER"
    )
    assert result["revised_prompt"] == "original"
    assert result["confidence"] == 0
