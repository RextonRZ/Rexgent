from app.services.continuation_media import hold_media, r2v_media


def test_talking_hold_uses_first_frame_plus_driving_audio():
    # driving_audio is ONLY valid with first_frame (confirmed) — never first_clip
    m = hold_media(first_clip_url="clip.mp4", first_frame_url="f.png",
                   audio_url="a.wav", talking=True)
    assert m == [{"type": "first_frame", "url": "f.png"},
                 {"type": "driving_audio", "url": "a.wav"}]


def test_silent_hold_prefers_first_clip_for_motion():
    m = hold_media(first_clip_url="clip.mp4", first_frame_url="f.png",
                   audio_url=None, talking=False)
    assert m == [{"type": "first_clip", "url": "clip.mp4"}]


def test_silent_hold_falls_back_to_first_frame():
    m = hold_media(first_clip_url=None, first_frame_url="f.png",
                   audio_url=None, talking=False)
    assert m == [{"type": "first_frame", "url": "f.png"}]


def test_talking_without_audio_or_frame_falls_back_to_continuation():
    # can't lip-sync without both frame and audio -> plain continuation
    m = hold_media(first_clip_url="clip.mp4", first_frame_url="f.png",
                   audio_url=None, talking=True)
    assert m == [{"type": "first_clip", "url": "clip.mp4"}]


def test_hold_with_nothing_returns_none():
    assert hold_media(first_clip_url=None, first_frame_url=None,
                      audio_url=None, talking=False) is None


def test_r2v_media_is_ref_stack_when_no_first_frame():
    stack = [{"type": "reference_image", "url": "face.png"},
             {"type": "reference_image", "url": "outfit.png"}]
    assert r2v_media(stack, first_frame_url=None) == stack


def test_r2v_media_prepends_first_frame_for_joint_control():
    stack = [{"type": "reference_image", "url": "face.png"}]
    assert r2v_media(stack, first_frame_url="prev.png") == [
        {"type": "first_frame", "url": "prev.png"},
        {"type": "reference_image", "url": "face.png"}]


def test_r2v_media_empty_returns_none():
    assert r2v_media(None, first_frame_url=None) is None
