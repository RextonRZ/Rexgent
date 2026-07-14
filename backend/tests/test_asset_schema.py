import pytest
from app.assets.schema import AssetMeta, MusicMeta


def test_asset_meta_optional_fields_have_defaults():
    m = AssetMeta(id="x", title="X", filename="x.mp3", type="music")
    assert m.tags == [] and m.license is None


def test_music_meta_extra_fields_allowed():
    m = MusicMeta(id="x", title="Sad Piano", filename="sad_piano.mp3", type="music",
                  mood="sadness", scene_tags=["breakup"], intensity=2,
                  something_new="future-proof")
    assert m.mood == "sadness"
    assert m.model_dump()["something_new"] == "future-proof"


def test_music_meta_missing_required_raises():
    with pytest.raises(Exception):
        MusicMeta(id="x", title="X", filename="x.mp3", type="music")
