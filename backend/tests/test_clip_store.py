import app.services.clip_store as cs


def test_persist_clip_rehosts_to_oss(monkeypatch):
    class R:
        content = b"MP4DATA"

    monkeypatch.setattr(cs.httpx, "get", lambda *a, **k: R())

    class FakeOSS:
        def __init__(self, settings):
            pass

        def get_project_path(self, pid, kind, name):
            return f"{pid}/{kind}/{name}"

        def upload_bytes(self, data, key, content_type=None):
            assert data == b"MP4DATA"
            assert content_type == "video/mp4"
            return f"https://oss/{key}"

    monkeypatch.setattr(cs, "OSSManager", FakeOSS)
    out = cs.persist_clip_url("p1", "shot_x", "http://dash/x.mp4?Expires=1")
    assert out.startswith("https://oss/p1/clips/shot_x_")
    assert out.endswith(".mp4")


def test_persist_clip_falls_back_on_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(cs.httpx, "get", boom)
    # keep the (expiring) original rather than losing the clip entirely
    assert cs.persist_clip_url("p1", "shot_x", "http://dash/x.mp4") == "http://dash/x.mp4"
