from app.services.music_suggest import derive_mood


def test_genre_maps_to_mood():
    assert derive_mood(genre="romance", beats=[]) == "romance"
    assert derive_mood(genre="thriller", beats=[]) == "thriller"


def test_beat_keyword_overrides_when_genre_unknown():
    assert derive_mood(genre="unknowngenre", beats=["a tearful goodbye"]) == "sadness"


def test_defaults_to_daily():
    assert derive_mood(genre=None, beats=[]) == "daily"
