from app.models.line_audio import LineAudio
from app.models.character import Character


def test_line_audio_columns():
    cols = LineAudio.__table__.columns.keys()
    for c in ["id", "project_id", "scene_number", "line_index", "character_name",
              "text", "voice_id", "audio_url", "duration_seconds"]:
        assert c in cols


def test_character_voice_columns():
    cols = Character.__table__.columns.keys()
    for c in ["voice_id", "voice_model", "voice_source", "voice_sample_url"]:
        assert c in cols
