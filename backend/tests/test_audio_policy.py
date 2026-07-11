from app.services.audio_policy import keep_clip_audio, SPEECH_KEEP_THRESHOLD, BED_VOLUME


def test_non_dialogue_chunks_always_keep_their_soundtrack():
    assert keep_clip_audio(False, None) is True
    assert keep_clip_audio(False, 0.9) is True  # even a talky track: no TTS to clash


def test_clean_dialogue_track_survives_as_the_bed():
    # the whole point: music/ambience/SFX no longer die with the fake speech
    assert keep_clip_audio(True, 0.0) is True
    assert keep_clip_audio(True, SPEECH_KEEP_THRESHOLD) is True


def test_speech_polluted_dialogue_track_is_muted():
    assert keep_clip_audio(True, SPEECH_KEEP_THRESHOLD + 0.01) is False
    assert keep_clip_audio(True, 0.8) is False


def test_unmeasurable_track_stays_muted_on_dialogue():
    # no VAD / no audio stream -> can't rule out fake speech -> safe mute
    assert keep_clip_audio(True, None) is False


def test_bed_volume_sits_under_the_voice():
    assert 0.0 < BED_VOLUME < 1.0
