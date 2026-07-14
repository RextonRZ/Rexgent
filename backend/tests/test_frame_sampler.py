import shutil
import subprocess

import pytest

from app.services.frame_sampler import (
    even_timestamps,
    extract_first_frame,
    extract_last_frame,
)


def test_even_timestamps_three():
    ts = even_timestamps(duration=8.0, count=3)
    assert len(ts) == 3
    assert ts[0] > 0 and ts[-1] < 8.0
    assert ts == sorted(ts)


def test_even_timestamps_zero_duration():
    assert even_timestamps(duration=0.0, count=3) == []


def test_even_timestamps_zero_count():
    assert even_timestamps(duration=8.0, count=0) == []


def test_even_timestamps_spacing():
    ts = even_timestamps(duration=12.0, count=3)
    assert ts == [3.0, 6.0, 9.0]


@pytest.fixture
def sample_clip(tmp_path):
    # a real (tiny) animated mp4. testsrc's moving pattern + on-screen timer means
    # frame 0 and the final frame differ, so it exercises both extractors honestly.
    # The -sseof recipe in extract_last_frame must also survive container durations
    # that overshoot the last packet, which killed every frame anchor (and with them
    # wan continuations, lip-sync and posters) in production.
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed")
    clip = str(tmp_path / "clip.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=64x64:rate=12",
         "-pix_fmt", "yuv420p", clip],
        capture_output=True, timeout=30, check=True)
    return clip


def test_extract_last_frame_returns_final_frame_bytes(sample_clip):
    data = extract_last_frame(sample_clip)
    assert data and len(data) > 500
    assert data.startswith(b"\xff\xd8")  # JPEG magic


def test_extract_first_frame_is_exposed():
    from app.services import frame_sampler
    assert hasattr(frame_sampler, "extract_first_frame")


def test_extract_first_frame_and_last_frame_have_same_signature():
    import inspect
    from app.services import frame_sampler
    first = inspect.signature(frame_sampler.extract_first_frame)
    last = inspect.signature(frame_sampler.extract_last_frame)
    assert list(first.parameters) == list(last.parameters)


def test_extract_first_frame_returns_first_frame_bytes(sample_clip):
    data = extract_first_frame(sample_clip)
    assert data is not None
    assert data.startswith(b"\xff\xd8")  # JPEG magic
    assert len(data) > 500
    # really frame 0, not the last: on an animated clip the two frames differ
    assert data != extract_last_frame(sample_clip)
