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
