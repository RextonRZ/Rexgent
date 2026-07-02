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
