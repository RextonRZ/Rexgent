from app.config import Settings


def test_wan_primary_defaults_off():
    assert Settings(_env_file=None).wan_primary is False
