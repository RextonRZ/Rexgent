from app.config import Settings


def test_director_engine_defaults_off():
    assert Settings().director_engine is False
