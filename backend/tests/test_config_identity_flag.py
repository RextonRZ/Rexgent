from app.config import Settings


def test_identity_routing_v2_defaults_off():
    s = Settings(_env_file=None)
    assert s.identity_routing_v2 is False


def test_videoedit_model_present():
    s = Settings(_env_file=None)
    assert s.qwen_wan_videoedit_model == "wan2.7-videoedit"
