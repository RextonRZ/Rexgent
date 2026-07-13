from app.config import Settings


def test_multishot_disabled_by_default():
    assert Settings(_env_file=None).multishot_enabled is False


def test_multishot_caps():
    s = Settings(_env_file=None)
    assert s.multishot_max_shots == 3
    assert s.multishot_max_duration == 15
