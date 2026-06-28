from app.services.frame_sampler import even_timestamps


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
