import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.character_extractor import CharacterExtractor


@pytest.mark.asyncio
async def test_extract_returns_characters():
    extractor = CharacterExtractor.__new__(CharacterExtractor)
    extractor.qwen = MagicMock()
    extractor.qwen.chat_json = AsyncMock(return_value=[
        {
            "name": "YUKI",
            "role": "PROTAGONIST",
            "first_appearance_scene": 1,
            "gender": "female",
            "estimated_age": "late 30s",
            "physical_description": "sharp features, short black hair",
            "personality_summary": "Guarded detective with trust issues.",
            "key_dialogue_samples": ["I don't trust machines."],
            "speech_pattern": "terse",
            "emotional_arc": {"start": "guarded", "midpoint": "conflicted", "end": "accepting"},
            "relationships": ["partner to ARIA"],
        }
    ])
    extractor.prompt_template = "placeholder"

    result = await extractor.extract(script_json={"scenes": []})
    assert len(result) == 1
    assert result[0]["name"] == "YUKI"
    assert result[0]["role"] == "PROTAGONIST"


@pytest.mark.asyncio
async def test_extract_handles_non_list():
    extractor = CharacterExtractor.__new__(CharacterExtractor)
    extractor.qwen = MagicMock()
    extractor.qwen.chat_json = AsyncMock(return_value={"not": "a list"})
    extractor.prompt_template = "placeholder"

    result = await extractor.extract(script_json={"scenes": []})
    assert result == []


@pytest.mark.asyncio
async def test_missing_gender_falls_back_to_honorifics():
    # the model returned gender null for half the cast once — MR. ROARKE got a
    # female voice. Honorifics in the name settle it deterministically.
    extractor = CharacterExtractor.__new__(CharacterExtractor)
    extractor.qwen = MagicMock()
    extractor.qwen.chat_json = AsyncMock(return_value=[
        {"name": "MR. ROARKE", "gender": None},
        {"name": "MRS. COLE", "gender": ""},
        {"name": "KAITO", "gender": None},        # no honorific -> left as-is
        {"name": "LADY WHISTLE", "gender": None},
        {"name": "GWEN", "gender": "female"},     # explicit stays untouched
    ])
    extractor.prompt_template = "placeholder"

    out = await extractor.extract(script_json={"scenes": []})
    by = {c["name"]: c.get("gender") for c in out}
    assert by["MR. ROARKE"] == "male"
    assert by["MRS. COLE"] == "female"
    assert by["LADY WHISTLE"] == "female"
    assert by["KAITO"] is None
    assert by["GWEN"] == "female"


def test_normalize_extracted_maps_chinese_enum_values():
    # a zh run answers the schema in Chinese; downstream checks compare
    # against the English enums (voice pick by gender, role ordering)
    from app.services.character_extractor import normalize_extracted
    data = [{"name": "小雨", "gender": "女", "role": "主角"},
            {"name": "大明", "gender": "男性", "role": "配角"},
            {"name": "Anna", "gender": "female", "role": "protagonist"}]
    out = normalize_extracted(data)
    assert out[0]["gender"] == "female" and out[0]["role"] == "PROTAGONIST"
    assert out[1]["gender"] == "male" and out[1]["role"] == "SUPPORTING"
    assert out[2]["gender"] == "female" and out[2]["role"] == "PROTAGONIST"


def test_normalize_extracted_leaves_unknown_values_alone():
    from app.services.character_extractor import normalize_extracted
    data = [{"name": "X", "gender": None, "role": "ANTAGONIST"}]
    out = normalize_extracted(data)
    assert out[0]["gender"] is None
    assert out[0]["role"] == "ANTAGONIST"


def test_missing_from_cast_finds_the_dropped_pet():
    # the imported zh script's scene rosters list 雪球, but the one-pass
    # extraction dropped it — the roster diff must surface exactly that name
    from app.services.character_extractor import missing_from_cast
    script = {"scenes": [
        {"scene_number": 1, "characters_present": ["安吉琳", "玛丽"]},
        {"scene_number": 2, "characters_present": ["安吉琳", "雪球", "路人"]},
    ]}
    cast = [{"name": "安吉琳"}, {"name": "玛丽"}]
    assert missing_from_cast(script, cast) == ["雪球"]   # 路人 is a placeholder


def test_missing_from_cast_reads_characters_mentioned_too():
    # the real imported-script failure: the structurer listed 雪球 ONLY in the
    # script-level characters_mentioned — every scene roster omitted it — so a
    # roster-only diff had no signal and the pet stayed out of the cast
    from app.services.character_extractor import missing_from_cast
    script = {"scenes": [
        {"scene_number": 1, "characters_present": ["安吉琳", "玛丽"]},
        {"scene_number": 2, "characters_present": ["安吉琳", "玛丽"]},
    ], "characters_mentioned": ["雪球"]}
    cast = [{"name": "安吉琳"}, {"name": "玛丽"}]
    assert missing_from_cast(script, cast) == ["雪球"]


def test_missing_from_cast_ignores_variants_of_extracted_names():
    # 'KERRY (ON SCREEN)' is KERRY — a stage-qualified variant is not missing
    from app.services.character_extractor import missing_from_cast
    script = {"scenes": [{"characters_present": ["KERRY (ON SCREEN)", "EIRIK"]}]}
    cast = [{"name": "Kerry"}, {"name": "Eirik Halden"}]
    assert missing_from_cast(script, cast) == []


@pytest.mark.asyncio
async def test_extract_retries_names_the_first_pass_missed():
    # first pass returns the humans only; the backstop confronts the model
    # with the roster names it skipped and merges what comes back
    extractor = CharacterExtractor.__new__(CharacterExtractor)
    extractor.qwen = MagicMock()
    extractor.qwen.chat_json = AsyncMock(side_effect=[
        [{"name": "安吉琳", "gender": "female", "role": "PROTAGONIST"}],
        [{"name": "雪球", "gender": "male", "role": "SUPPORTING",
          "physical_description": "一只蓬松的白色小狗"}],
    ])
    extractor.prompt_template = "placeholder"
    script = {"scenes": [{"characters_present": ["安吉琳", "雪球"]}]}
    out = await extractor.extract(script_json=script, language="zh")
    names = [c["name"] for c in out]
    assert names == ["安吉琳", "雪球"]
    assert extractor.qwen.chat_json.await_count == 2
    retry_msg = extractor.qwen.chat_json.await_args_list[1].kwargs["messages"][1]["content"]
    assert "雪球" in retry_msg


@pytest.mark.asyncio
async def test_extract_makes_no_second_call_when_cast_is_complete():
    extractor = CharacterExtractor.__new__(CharacterExtractor)
    extractor.qwen = MagicMock()
    extractor.qwen.chat_json = AsyncMock(return_value=[
        {"name": "安吉琳", "gender": "female"}])
    extractor.prompt_template = "placeholder"
    script = {"scenes": [{"characters_present": ["安吉琳"]}]}
    out = await extractor.extract(script_json=script, language="zh")
    assert [c["name"] for c in out] == ["安吉琳"]
    assert extractor.qwen.chat_json.await_count == 1


@pytest.mark.asyncio
async def test_extract_retry_never_duplicates_existing_cast():
    # a retry that re-lists an already-extracted character must not duplicate
    extractor = CharacterExtractor.__new__(CharacterExtractor)
    extractor.qwen = MagicMock()
    extractor.qwen.chat_json = AsyncMock(side_effect=[
        [{"name": "安吉琳"}],
        [{"name": "安吉琳"}, {"name": "雪球"}],
    ])
    extractor.prompt_template = "placeholder"
    script = {"scenes": [{"characters_present": ["安吉琳", "雪球"]}]}
    out = await extractor.extract(script_json=script, language="zh")
    assert [c["name"] for c in out] == ["安吉琳", "雪球"]
