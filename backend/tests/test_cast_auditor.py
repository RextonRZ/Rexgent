import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.cast_auditor import CastAuditor, apply_cast_audit


@pytest.mark.asyncio
async def test_audit_parses_removals():
    a = CastAuditor.__new__(CastAuditor)
    a.qwen = MagicMock()
    a.qwen.chat_json = AsyncMock(return_value={
        "removals": [{"shot_number": 1, "remove": ["雪球"]}]})
    a.prompt_template = "placeholder"
    out = await a.audit({"scene_number": 1}, [
        {"shot_number": 1, "action": "安吉琳抱着空兔笼哭泣，说雪球不见了。",
         "dialogue": None, "characters_in_frame": ["安吉琳", "雪球"]}])
    assert out == {1: ["雪球"]}


@pytest.mark.asyncio
async def test_audit_tolerates_garbage():
    a = CastAuditor.__new__(CastAuditor)
    a.qwen = MagicMock()
    a.qwen.chat_json = AsyncMock(return_value=["junk"])
    a.prompt_template = "placeholder"
    assert await a.audit({}, []) == {}


def test_apply_cast_audit_drops_but_protects_the_speaker():
    shots = [
        {"shot_number": 1, "dialogue": "妈妈，雪球不见了。",
         "characters_in_frame": ["安吉琳", "雪球"],
         "subjects": [{"character": "安吉琳"}, {"character": "雪球"}]},
        {"shot_number": 2, "dialogue": None,
         "characters_in_frame": ["安吉琳", "玛丽"],
         "subjects": [{"character": "安吉琳"}, {"character": "玛丽"}]},
    ]
    lines = [{"character": "安吉琳", "line": "妈妈，雪球不见了。"}]
    notes = apply_cast_audit(
        shots, {1: ["雪球", "安吉琳"], 2: ["玛丽"]}, dialogue_lines=lines)
    assert shots[0]["characters_in_frame"] == ["安吉琳"]   # speaker survived
    assert shots[1]["characters_in_frame"] == ["安吉琳"]
    assert [s["character"] for s in shots[1]["subjects"]] == ["安吉琳"]
    assert len(notes) == 2
