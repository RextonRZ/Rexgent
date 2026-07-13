from app.config import Settings


def test_repair_disabled_by_default():
    s = Settings(_env_file=None)
    assert s.repair_enabled is False


def test_repair_max_renders_default():
    s = Settings(_env_file=None)
    assert s.repair_max_renders == 2
