from app.config import Settings


def test_anchor_lipsync_disabled_by_default():
    assert Settings(_env_file=None).anchor_lipsync_enabled is False
