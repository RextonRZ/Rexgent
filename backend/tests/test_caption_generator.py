from app.services.caption_generator import CaptionGenerator


def test_srt_timing_and_skips_silent_clips():
    gen = CaptionGenerator()
    srt = gen.generate_srt([
        {"dialogue": None, "duration": 4},          # establishing, no caption
        {"dialogue": "Something's wrong.", "duration": 5},
        {"dialogue": "I know what you are.", "duration": 6},
    ])
    assert "Something's wrong." in srt
    assert "I know what you are." in srt
    # First captioned line starts at 4s (after the silent 4s clip).
    assert "00:00:04,000 --> 00:00:09,000" in srt
    # Second caption runs 9s -> 15s.
    assert "00:00:09,000 --> 00:00:15,000" in srt


def test_srt_empty_when_no_dialogue():
    gen = CaptionGenerator()
    srt = gen.generate_srt([{"dialogue": None, "duration": 5}])
    assert srt == ""


def test_format_time():
    gen = CaptionGenerator()
    assert gen._format_time(0) == "00:00:00,000"
    assert gen._format_time(65.5) == "00:01:05,500"


def test_segment_srt_uses_placed_audio_timing():
    gen = CaptionGenerator()
    srt = gen.generate_srt_from_segments([
        {"start": 5.0, "duration": 2.0, "text": "Something's wrong."},
        {"start": 10.0, "duration": 1.5, "text": "I know what you are."},
        {"start": 2.0, "duration": 0.0, "audio_path": "x"},  # no text -> skipped
    ])
    # caption appears when the LINE is spoken, not when the shot starts
    assert "00:00:05,000 --> 00:00:07,000" in srt
    assert "00:00:10,000 --> 00:00:11,500" in srt
    assert "Something's wrong." in srt


def test_segment_srt_never_overlaps_next_line():
    gen = CaptionGenerator()
    srt = gen.generate_srt_from_segments([
        {"start": 0.0, "duration": 6.0, "text": "A very long line."},
        {"start": 3.0, "duration": 2.0, "text": "Interruption."},
    ])
    # first caption is clipped just before the second begins
    assert "00:00:00,000 --> 00:00:02,950" in srt


def test_segment_srt_empty_when_no_text():
    gen = CaptionGenerator()
    assert gen.generate_srt_from_segments([{"start": 0.0, "duration": 2.0}]) == ""
