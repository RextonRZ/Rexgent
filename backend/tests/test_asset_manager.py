import json
from pathlib import Path
import pytest
from app.services.asset_manager import AssetManager


def _write(root: Path, rel: str, meta: dict):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"FAKEAUDIO")
    p.with_suffix(".json").write_text(json.dumps(meta))


@pytest.fixture
def library(tmp_path):
    _write(tmp_path, "music/sadness/sad_piano.mp3", {
        "id": "sad_piano", "title": "Sad Piano", "filename": "sad_piano.mp3",
        "type": "music", "mood": "sadness", "scene_tags": ["breakup"],
        "intensity": 2, "duration": 30})
    _write(tmp_path, "music/happy/sunny.mp3", {
        "id": "sunny", "title": "Sunny", "filename": "sunny.mp3", "type": "music",
        "mood": "happy", "scene_tags": ["wedding"], "intensity": 3, "duration": 60})
    _write(tmp_path, "music/sadness/broken.json", {"bad": "no required fields"})
    m = AssetManager(root=tmp_path)
    m.scan()
    return m


def test_scan_indexes_valid_music_and_skips_invalid(library):
    music = library.find_music()
    assert {a.id for a in music} == {"sad_piano", "sunny"}


def test_find_music_by_mood(library):
    r = library.find_music(mood="sadness")
    assert [a.id for a in r] == ["sad_piano"]


def test_find_music_by_scene_and_duration(library):
    r = library.find_music(scene="breakup", max_duration=40)
    assert [a.id for a in r] == ["sad_piano"]


def test_find_music_intensity(library):
    assert [a.id for a in library.find_music(intensity=3)] == ["sunny"]


def test_random_match_returns_matching(library):
    a = library.random_match("music", mood="happy")
    assert a.id == "sunny"


def test_random_match_none_when_empty(library):
    assert library.random_match("music", mood="horror") is None


def test_local_path_points_at_the_file(library):
    a = library.find_music(mood="sadness")[0]
    assert library.local_path(a).name == "sad_piano.mp3"
    assert library.local_path(a).exists()
