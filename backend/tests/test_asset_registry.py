from app.assets.registry import ASSET_TYPES, categories_for


def test_all_eleven_types_present():
    assert set(ASSET_TYPES) == {
        "music", "sfx", "ambience", "vfx", "transitions", "overlays",
        "subtitles", "fonts", "luts", "stickers", "templates"}


def test_music_moods_present():
    moods = categories_for("music")
    for m in ("romance", "sadness", "happy", "thriller", "horror"):
        assert m in moods


def test_categories_for_unknown_type_is_empty():
    assert categories_for("nope") == []
