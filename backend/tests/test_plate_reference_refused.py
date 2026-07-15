"""When the image-edit service refuses the reference face (DataInspectionFailed),
the plate generator must NOT fall back to a paid text-to-image render that ships a
stranger. It reuses the already-valid reference plate and flags it, so the user is
never billed for an unusable plate."""
import asyncio

from app.services.plate_generator import PlateGenerator, ReferenceEditRefused


class _FakeQwen:
    def __init__(self):
        self.t2i_called = False

    async def edit_image(self, *a, **k):
        raise Exception("DataInspectionFailed: reference refused by content filter")

    async def generate_image(self, *a, **k):
        self.t2i_called = True
        return "http://example/text-to-image-stranger.png"


def _pg(qwen):
    pg = object.__new__(PlateGenerator)  # bypass the heavy FaceEmbedder init
    pg.qwen = qwen
    pg.last_face_preserved = None
    return pg


def test_refused_edit_reuses_reference_and_never_spends_on_t2i():
    q = _FakeQwen()
    pg = _pg(q)
    ref = "http://oss/anna_identity_plate.png"
    url, vec = asyncio.run(pg.generate_and_store_plate(
        "proj", "character", "Anna_dinner dress", "waist-up costume plate",
        base_image_url=ref, match_vector=[0.1, 0.2, 0.3]))
    assert url == ref                       # reused the reference plate
    assert q.t2i_called is False            # NO wasted text-to-image render
    assert pg.last_face_preserved is False  # caller reads this -> ref_rejected
    assert vec == [0.1, 0.2, 0.3]           # keeps the reference's face vector


def test_render_once_raises_refused_instead_of_falling_back():
    pg = _pg(_FakeQwen())
    import pytest
    with pytest.raises(ReferenceEditRefused):
        asyncio.run(pg._render_once("character", "k", "p", None,
                                    "http://oss/ref.png", False))
    assert pg.qwen.t2i_called is False
