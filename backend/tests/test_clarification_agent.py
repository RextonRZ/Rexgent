import pytest
from unittest.mock import AsyncMock
from app.agents.clarification_agent import ClarificationAgent, needs_pause


@pytest.mark.asyncio
async def test_assess_returns_questions():
    a = ClarificationAgent.__new__(ClarificationAgent)
    a.qwen = type("Q", (), {})()
    a.qwen.chat_json = AsyncMock(return_value={"confidence": 0.4,
        "ambiguities": [{"topic": "partner", "why": "unclear", "question": "Robot or human?", "options": ["robot", "human"]}]})
    a.prompt_template = "x"
    out = await a.assess({"scenes": []}, [{"name": "Detective"}])
    assert out["ambiguities"][0]["topic"] == "partner"


def test_needs_pause_logic():
    assert needs_pause({"ambiguities": [{"topic": "x"}]}, auto_clarify=False) is True
    assert needs_pause({"ambiguities": [{"topic": "x"}]}, auto_clarify=True) is False
    assert needs_pause({"ambiguities": []}, auto_clarify=False) is False
