import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.dialogue_synthesizer import DialogueSynthesizer


@pytest.mark.asyncio
async def test_synthesize_creates_line_rows(monkeypatch):
    ds = DialogueSynthesizer.__new__(DialogueSynthesizer)
    ds.qwen = MagicMock(); ds.qwen.synthesize_speech = AsyncMock(return_value=b"RIFF")
    ds.oss = MagicMock()
    ds.oss.get_project_path = MagicMock(return_value="p/audio/x.wav")
    ds.oss.upload_bytes = MagicMock(return_value="https://oss/x.wav")
    monkeypatch.setattr("app.services.dialogue_synthesizer.probe_duration", lambda b: 1.5)
    rows = await ds.synthesize_lines(
        project_id="p1",
        scenes=[{"number": 1, "dialogue_json": [{"character": "Mia", "line": "Hi"}]}],
        voice_by_name={"Mia": {"voice_id": "v1", "voice_model": "m"}})
    assert rows[0]["audio_url"] == "https://oss/x.wav"
    assert rows[0]["duration_seconds"] == 1.5
    assert rows[0]["scene_number"] == 1 and rows[0]["line_index"] == 0


@pytest.mark.asyncio
async def test_transient_tts_failure_is_retried_then_succeeds(monkeypatch):
    # A flaky TTS call fails twice then succeeds — the line must still be
    # produced, not silently dropped (which would lose its voice AND caption).
    ds = DialogueSynthesizer.__new__(DialogueSynthesizer)
    ds.qwen = MagicMock()
    ds.qwen.synthesize_speech = AsyncMock(
        side_effect=[RuntimeError("503"), RuntimeError("503"), b"RIFF"])
    ds.oss = MagicMock()
    ds.oss.get_project_path = MagicMock(return_value="p/audio/x.wav")
    ds.oss.upload_bytes = MagicMock(return_value="https://oss/x.wav")
    ds.db = None
    monkeypatch.setattr("app.services.dialogue_synthesizer.probe_duration", lambda b: 1.0)
    monkeypatch.setattr("app.services.dialogue_synthesizer.asyncio.sleep", AsyncMock())
    rows = await ds.synthesize_lines(
        project_id="p1",
        scenes=[{"number": 1, "dialogue_json": [{"character": "Mia", "line": "Hi"}]}],
        voice_by_name={"Mia": {"voice_id": "v1"}})
    assert len(rows) == 1
    assert rows[0]["audio_url"] == "https://oss/x.wav"
    assert ds.qwen.synthesize_speech.await_count == 3


@pytest.mark.asyncio
async def test_persistent_tts_failure_skips_line_without_crashing(monkeypatch):
    # Every attempt fails — the batch survives and simply omits that line, so
    # the export's missing-line detection can retry it on the next pass.
    ds = DialogueSynthesizer.__new__(DialogueSynthesizer)
    ds.qwen = MagicMock()
    ds.qwen.synthesize_speech = AsyncMock(side_effect=RuntimeError("dead"))
    ds.oss = MagicMock()
    ds.oss.get_project_path = MagicMock(return_value="p/audio/x.wav")
    ds.oss.upload_bytes = MagicMock(return_value="https://oss/x.wav")
    ds.db = None
    monkeypatch.setattr("app.services.dialogue_synthesizer.asyncio.sleep", AsyncMock())
    rows = await ds.synthesize_lines(
        project_id="p1",
        scenes=[{"number": 1, "dialogue_json": [
            {"character": "Mia", "line": "Hi"},
            {"character": "Rex", "line": "Bye"},
        ]}],
        voice_by_name={"Mia": {"voice_id": "v1"}, "Rex": {"voice_id": "v2"}})
    assert rows == []                                # both dropped, no crash
    assert ds.qwen.synthesize_speech.await_count == 6  # 2 lines x 3 attempts


@pytest.mark.asyncio
async def test_only_characters_filters_but_keeps_line_indices(monkeypatch):
    # Recast Mia: only her lines re-synthesize, and her line_index stays the
    # position in the FULL dialogue list (1, not 0) so timeline placement holds.
    ds = DialogueSynthesizer.__new__(DialogueSynthesizer)
    ds.qwen = MagicMock(); ds.qwen.synthesize_speech = AsyncMock(return_value=b"RIFF")
    ds.oss = MagicMock()
    ds.oss.get_project_path = MagicMock(return_value="p/audio/x.wav")
    ds.oss.upload_bytes = MagicMock(return_value="https://oss/x.wav")
    monkeypatch.setattr("app.services.dialogue_synthesizer.probe_duration", lambda b: 1.0)
    rows = await ds.synthesize_lines(
        project_id="p1",
        scenes=[{"number": 1, "dialogue_json": [
            {"character": "Rex", "line": "Stop."},
            {"character": "Mia", "line": "No."},
        ]}],
        voice_by_name={"Rex": {"voice_id": "Eric"}, "Mia": {"voice_id": "new-clone"}},
        only_characters={"Mia"})
    assert len(rows) == 1                      # Rex's line untouched
    assert rows[0]["character_name"] == "Mia"
    assert rows[0]["line_index"] == 1          # full-list index, not 0
    assert rows[0]["voice_id"] == "new-clone"  # synthesized with the NEW voice
    ds.qwen.synthesize_speech.assert_awaited_once()


def test_line_direction_merges_parenthetical_and_beat():
    from app.services.dialogue_synthesizer import line_direction
    assert line_direction({"line": "(whispering) I saw you."}) == "whispering"
    assert line_direction({"line": "I saw you.",
                           "direction": "confusion and hurt"}) == "confusion and hurt"
    assert line_direction({"line": "(sobbing) Why?",
                           "direction": "betrayal"}) == "sobbing, betrayal"
    assert line_direction({"line": "Hello."}) is None


def test_scene_line_beats_orders_by_shot_number():
    # the k-th dialogue line pairs with the k-th speaking shot (the same
    # convention placement uses), so beats come back in shot order
    from app.services.dialogue_synthesizer import scene_line_beats
    shots = [
        {"number": 2, "dialogue": "line b", "emotional_beat": "beat B"},
        {"number": 1, "dialogue": "line a", "emotional_beat": "beat A"},
        {"number": 3, "dialogue": "", "emotional_beat": "silent"},
    ]
    assert scene_line_beats(shots) == ["beat A", "beat B"]
