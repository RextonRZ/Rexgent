from app.config import Settings


def test_director_engine_defaults_off():
    # the CODE default is off, independent of a developer's local .env (which may
    # set DIRECTOR_ENGINE=true to try the engine) — read the field default only.
    assert Settings(_env_file=None).director_engine is False
