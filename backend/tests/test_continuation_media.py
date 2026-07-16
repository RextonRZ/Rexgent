from app.services.continuation_media import hold_media, r2v_media


def test_silent_hold_prefers_first_clip_for_motion():
    m = hold_media(first_clip_url="clip.mp4", first_frame_url="f.png")
    assert m == [{"type": "first_clip", "url": "clip.mp4"}]


def test_silent_hold_falls_back_to_first_frame():
    m = hold_media(first_clip_url=None, first_frame_url="f.png")
    assert m == [{"type": "first_frame", "url": "f.png"}]


def test_hold_with_nothing_returns_none():
    assert hold_media(first_clip_url=None, first_frame_url=None) is None


class TestHoldMediaDurationGuard:
    """first_clip carries a DashScope hard constraint: the requested duration
    must EXCEED the seed clip's length or the task fails server-side
    ('first_clip duration (5.16s after trim) must be less than the requested
    duration (3s)') — which killed every 3s beat that followed a 5s clip."""

    def test_short_request_falls_back_to_first_frame(self):
        media = hold_media(first_clip_url="clip.mp4", first_frame_url="frame.jpg",
                           want_seconds=3, first_clip_seconds=5)
        assert media == [{"type": "first_frame", "url": "frame.jpg"}]

    def test_long_request_keeps_first_clip(self):
        media = hold_media(first_clip_url="clip.mp4", first_frame_url="frame.jpg",
                           want_seconds=10, first_clip_seconds=5)
        assert media == [{"type": "first_clip", "url": "clip.mp4"}]

    def test_equal_durations_are_not_safe(self):
        media = hold_media(first_clip_url="clip.mp4", first_frame_url="frame.jpg",
                           want_seconds=5, first_clip_seconds=5)
        assert media[0]["type"] == "first_frame"

    def test_unknown_seed_length_with_known_want_is_conservative(self):
        media = hold_media(first_clip_url="clip.mp4", first_frame_url="frame.jpg",
                           want_seconds=3)
        assert media[0]["type"] == "first_frame"

    def test_nothing_to_continue_from_with_durations(self):
        assert hold_media(want_seconds=3) is None


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


def test_r2v_media_lone_first_frame_returns_none():
    # no reference images -> not an r2v job, even with a first_frame
    assert r2v_media([], first_frame_url="p.png") is None


def test_r2v_media_dedupes_first_frame_from_stack():
    # the prev frame is already in the stack as a reference_image; don't send it twice
    stack = [{"type": "reference_image", "url": "prev.png"},
             {"type": "reference_image", "url": "face.png"}]
    assert r2v_media(stack, first_frame_url="prev.png") == [
        {"type": "first_frame", "url": "prev.png"},
        {"type": "reference_image", "url": "face.png"}]
