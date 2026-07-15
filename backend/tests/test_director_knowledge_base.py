from app.director import knowledge_base as kb


def test_every_purpose_has_valid_sizes():
    for purpose, spec in kb.SHOT_PURPOSES.items():
        assert spec["sizes"], purpose
        assert all(s in kb.SHOT_SIZES for s in spec["sizes"]), purpose
        assert isinstance(spec["dialogue"], bool)


def test_non_verbal_purposes_carry_no_dialogue():
    for p in ("reaction", "insert", "establishing", "beat"):
        assert kb.SHOT_PURPOSES[p]["dialogue"] is False


def test_genre_lookup_and_default():
    assert kb.genre_look("thriller")["lens_bias"] == "85mm"
    # unknown genre -> the neutral default, never a KeyError
    assert kb.genre_look("no-such-genre") == kb.GENRE_LOOKS["_default"]


def test_every_genre_look_has_valid_light_quality():
    for genre, spec in kb.GENRE_LOOKS.items():
        assert "light_quality" in spec, genre
        assert spec["light_quality"] in kb.LIGHT_QUALITIES, genre
    assert kb.genre_look("thriller")["light_quality"] == "side"


def test_incompatible_pairs_flagged():
    assert kb.is_incompatible("EWS", "85mm")
    assert not kb.is_incompatible("CU", "85mm")


def test_alt_size_differs_and_fits_purpose():
    alt = kb.alt_size_for("MS", "dialogue")
    assert alt != "MS" and alt in kb.SHOT_PURPOSES["dialogue"]["sizes"]


def test_stylization_and_special_effect_catalogs_exist():
    assert "cinematic" in kb.STYLIZATIONS
    assert "noir" in kb.STYLIZATIONS
    assert "tilt_shift" in kb.SPECIAL_EFFECTS
    assert "time_lapse" in kb.SPECIAL_EFFECTS
    # every value is a human-readable description
    assert all(isinstance(v, str) and v for v in kb.STYLIZATIONS.values())
    assert all(isinstance(v, str) and v for v in kb.SPECIAL_EFFECTS.values())


def test_every_genre_look_has_valid_stylization():
    for genre, spec in kb.GENRE_LOOKS.items():
        assert "stylization" in spec, genre
        assert spec["stylization"] in kb.STYLIZATIONS, genre
    assert kb.genre_look("thriller")["stylization"] == "noir"
    assert kb.genre_look("no-such-genre")["stylization"] == "cinematic"


def test_advanced_camera_moves_present():
    for mv in ("ORBIT", "CRANE", "TRACKING", "COMPOUND"):
        assert mv in kb.CAMERA_MOVES
    # the existing moves are untouched
    assert "STATIC" in kb.CAMERA_MOVES and "DOLLY_IN" in kb.CAMERA_MOVES


def test_validity_helpers():
    assert kb.is_stylization("noir") and not kb.is_stylization("nope")
    assert kb.is_special_effect("tilt_shift") and not kb.is_special_effect("nope")
    assert not kb.is_stylization(None) and not kb.is_special_effect(None)
