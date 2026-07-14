import shutil
import subprocess

import pytest

from app.services.frame_sampler import even_timestamps, extract_last_frame


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


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_extract_last_frame_returns_final_frame_bytes(tmp_path):
    # a real (tiny) mp4: the -sseof recipe must survive container durations
    # that overshoot the last packet, which killed every frame anchor (and
    # with them wan continuations, lip-sync and posters) in production
    clip = str(tmp_path / "clip.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=64x64:rate=12",
         "-pix_fmt", "yuv420p", clip],
        capture_output=True, timeout=30, check=True)
    data = extract_last_frame(clip)
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
