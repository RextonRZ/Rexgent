import app.services.audio_policy as ap
from app.services.audio_policy import (BED_VOLUME, SPEECH_KEEP_THRESHOLD,
                                       bed_decision, keep_clip_audio)


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


def test_bed_decision_non_dialogue_passes_audio_through(monkeypatch):
    monkeypatch.setattr(ap, "speech_ratio", lambda p: 0.99)
    assert bed_decision("x.mp4", has_dialogue=False) == (False, None)


def test_bed_decision_vad_clean_keeps_bed_without_asr(monkeypatch):
    monkeypatch.setattr(ap, "speech_ratio", lambda p: 0.02)
    monkeypatch.setattr(ap, "transcribed_words",
                        lambda p: (_ for _ in ()).throw(AssertionError("ASR must not run")))
    assert bed_decision("x.mp4", has_dialogue=True) == (False, BED_VOLUME)


def test_bed_decision_asr_overrules_vad_music_bias(monkeypatch):
    # the production case: VAD screams speech at a wordless score
    monkeypatch.setattr(ap, "speech_ratio", lambda p: 0.99)
    monkeypatch.setattr(ap, "transcribed_words", lambda p: 0)
    assert bed_decision("x.mp4", has_dialogue=True) == (False, BED_VOLUME)


def test_bed_decision_real_words_still_mute(monkeypatch):
    monkeypatch.setattr(ap, "speech_ratio", lambda p: 0.99)
    monkeypatch.setattr(ap, "transcribed_words", lambda p: 9)
    assert bed_decision("x.mp4", has_dialogue=True) == (True, None)


def test_bed_decision_asr_failure_keeps_the_safe_mute(monkeypatch):
    monkeypatch.setattr(ap, "speech_ratio", lambda p: 0.99)
    monkeypatch.setattr(ap, "transcribed_words", lambda p: -1)
    assert bed_decision("x.mp4", has_dialogue=True) == (True, None)


def test_first_spoken_onset_skips_wordless_sentences():
    from app.services.audio_policy import first_spoken_onset
    # the recognizer emits empty-text sentences for half-heard music; their
    # timestamps are noise and must not become the onset
    sents = [{"text": "", "begin_time": 0},
             {"text": "  ", "begin_time": 500},
             {"text": "I can't do this anymore.", "begin_time": 2170}]
    assert first_spoken_onset(sents) == 2.17


def test_first_spoken_onset_none_without_words():
    from app.services.audio_policy import first_spoken_onset
    assert first_spoken_onset([{"text": "", "begin_time": 0}]) is None
    assert first_spoken_onset([]) is None


def test_spoken_span_covers_first_to_last_worded_sentence():
    from app.services.audio_policy import spoken_span
    sents = [{"text": "", "begin_time": 0, "end_time": 900},
             {"text": "I can't", "begin_time": 2170, "end_time": 3600},
             {"text": "do this anymore", "begin_time": 4000, "end_time": 5140}]
    assert spoken_span(sents) == (2.17, 2.97)
    assert spoken_span([{"text": "", "begin_time": 0}]) is None


def test_spoken_words_reads_the_word_grid():
    # fun-asr sentences carry per-word timestamps: the grid the lip warp
    # paces against, in seconds
    sentences = [{"text": "Snowy, where are you?", "begin_time": 1200,
                  "end_time": 3000,
                  "words": [
                      {"text": "Snowy,", "begin_time": 1200, "end_time": 1700},
                      {"text": "where", "begin_time": 1750, "end_time": 2100},
                      {"text": "are", "begin_time": 2100, "end_time": 2350},
                      {"text": "you?", "begin_time": 2400, "end_time": 3000},
                  ]}]
    from app.services.audio_policy import spoken_words
    assert spoken_words(sentences) == [(1.2, 1.7), (1.75, 2.1),
                                       (2.1, 2.35), (2.4, 3.0)]


def test_spoken_words_skips_wordless_music_sentences():
    from app.services.audio_policy import spoken_words
    assert spoken_words([{"text": "", "begin_time": 0, "words": [
        {"text": "", "begin_time": 0, "end_time": 400}]}]) == []
    assert spoken_words([{"text": "hi", "begin_time": 0}]) == []
