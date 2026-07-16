import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.plate_generator import PlateGenerator


@pytest.mark.asyncio
async def test_generate_and_store_plate_character_embeds_face():
    gen = PlateGenerator.__new__(PlateGenerator)
    gen.qwen = MagicMock()
    gen.qwen.generate_image = AsyncMock(return_value="https://img/raw.png")
    gen.oss = MagicMock()
    gen.oss.get_project_path = MagicMock(return_value="proj/plates/x.png")
    gen.oss.upload_bytes = MagicMock(return_value="https://oss/x.png")
    gen._fetch_bytes = MagicMock(return_value=b"imgbytes")
    gen.embedder = MagicMock()
    gen.embedder.extract = AsyncMock(return_value={"vector": [0.1] * 512, "description": {}})

    url, vector = await gen.generate_and_store_plate(
        project_id="p1", kind="character", key="Mia:uniform", prompt="navy uniform portrait")
    assert url == "https://oss/x.png"
    assert vector == [0.1] * 512
    # embedded the SAME bytes we uploaded (single download, no second fetch)
    gen.embedder.extract.assert_awaited_once()
    assert gen.embedder.extract.call_args.kwargs["image_bytes"] == b"imgbytes"


@pytest.mark.asyncio
async def test_generate_and_store_plate_location_skips_face():
    gen = PlateGenerator.__new__(PlateGenerator)
    gen.qwen = MagicMock()
    gen.qwen.generate_image = AsyncMock(return_value="https://img/raw.png")
    gen.oss = MagicMock()
    gen.oss.get_project_path = MagicMock(return_value="proj/plates/x.png")
    gen.oss.upload_bytes = MagicMock(return_value="https://oss/loc.png")
    gen._fetch_bytes = MagicMock(return_value=b"imgbytes")
    gen.embedder = MagicMock()
    gen.embedder.extract = AsyncMock()

    url, vector = await gen.generate_and_store_plate(
        project_id="p1", kind="location", key="coffee_shop", prompt="cozy cafe")
    assert url == "https://oss/loc.png"
    assert vector is None
    gen.embedder.extract.assert_not_called()


def test_subject_descriptor_keeps_numeric_age_without_gender():
    from app.services.plate_generator import subject_descriptor
    # gender missing but age '20s' — must still anchor a human adult, or the
    # model reads 'soft/delicate' face text as a child
    s = subject_descriptor(None, "20s", "soft, delicate features")
    assert s.startswith("a person around 20s")
    # non-numeric 'age' with no gender (e.g. a pet) keeps appearance-only
    dog = subject_descriptor("unknown", "dog age", "small white dog")
    assert dog == "small white dog"


@pytest.mark.asyncio
async def test_character_plate_edits_face_when_reference_given():
    gen = PlateGenerator.__new__(PlateGenerator)
    gen.qwen = MagicMock()
    gen.qwen.generate_image = AsyncMock(return_value="https://img/text.png")
    gen.qwen.edit_image = AsyncMock(return_value="https://img/edited.png")
    gen.oss = MagicMock()
    gen.oss.get_project_path = MagicMock(return_value="proj/plates/x.png")
    gen.oss.upload_bytes = MagicMock(return_value="https://oss/x.png")
    gen._fetch_bytes = MagicMock(return_value=b"imgbytes")
    gen.embedder = MagicMock()
    gen.embedder.extract = AsyncMock(return_value={"vector": [0.2] * 512, "description": {}})

    await gen.generate_and_store_plate(
        project_id="p1", kind="character", key="Mia:uniform",
        prompt="same person, navy uniform", base_image_url="https://oss/face.png")
    # a face reference routes through the image-edit path, not text-to-image
    gen.qwen.edit_image.assert_awaited_once()
    assert gen.qwen.edit_image.call_args.args[1] == "https://oss/face.png"
    gen.qwen.generate_image.assert_not_called()
    assert gen.last_face_preserved is True  # the shipped face IS the reference


@pytest.mark.asyncio
async def test_character_plate_reuses_reference_when_edit_refused():
    # When the edit model refuses the reference (e.g. DataInspectionFailed), do NOT
    # spend on a text-to-image fallback that ships a stranger's face — reuse the
    # already-valid reference plate instead so the user isn't billed for junk.
    gen = PlateGenerator.__new__(PlateGenerator)
    gen.qwen = MagicMock()
    gen.qwen.edit_image = AsyncMock(side_effect=RuntimeError("edit model 400"))
    gen.qwen.generate_image = AsyncMock(return_value="https://img/text.png")
    gen.oss = MagicMock()
    gen.oss.get_project_path = MagicMock(return_value="proj/plates/x.png")
    gen.oss.upload_bytes = MagicMock(return_value="https://oss/x.png")
    gen._fetch_bytes = MagicMock(return_value=b"imgbytes")
    gen.embedder = MagicMock()
    gen.embedder.extract = AsyncMock(return_value={"vector": [0.3] * 512, "description": {}})

    url, _ = await gen.generate_and_store_plate(
        project_id="p1", kind="character", key="Mia:uniform",
        prompt="same person, navy uniform", base_image_url="https://oss/face.png")
    assert url == "https://oss/face.png"          # reused the reference plate
    gen.qwen.generate_image.assert_not_awaited()  # NO wasted text-to-image render
    # the edit was refused, so callers badge the plate ref_rejected
    assert gen.last_face_preserved is False


@pytest.mark.asyncio
async def test_identity_mismatch_rerolls_and_keeps_the_closest_face():
    # attempt 1 renders a stranger (cosine 0.1 vs the reference); the plate is
    # re-rolled once and the better attempt (0.6) ships. One extra image, no
    # stranger in the character's costume.
    gen = PlateGenerator.__new__(PlateGenerator)
    gen.db = None
    gen.qwen = MagicMock()
    gen.qwen.edit_image = AsyncMock(side_effect=["https://img/a.png", "https://img/b.png"])
    gen.qwen.generate_image = AsyncMock()
    gen.oss = MagicMock()
    gen.oss.get_project_path = MagicMock(return_value="proj/plates/x.png")
    gen.oss.upload_bytes = MagicMock(return_value="https://oss/x.png")
    gen._fetch_bytes = MagicMock(side_effect=[b"stranger", b"match"])
    ref = [1.0] + [0.0] * 511
    stranger = [0.1] + [(1 - 0.1**2) ** 0.5] + [0.0] * 510   # cosine 0.1
    match = [0.6] + [(1 - 0.6**2) ** 0.5] + [0.0] * 510      # cosine 0.6
    gen.embedder = MagicMock()
    gen.embedder.model = MagicMock()
    gen.embedder.model.embed = MagicMock(side_effect=[stranger, match])
    gen.embedder.extract = AsyncMock(return_value={"vector": match, "description": {}})

    url, _ = await gen.generate_and_store_plate(
        project_id="p1", kind="character", key="Mia:uniform",
        prompt="same person, navy uniform",
        base_image_url="https://oss/face.png", match_vector=ref)
    assert gen.qwen.edit_image.await_count == 2       # re-rolled once
    assert gen.oss.upload_bytes.call_args.args[0] == b"match"  # best attempt ships
    assert url == "https://oss/x.png"


@pytest.mark.asyncio
async def test_identity_match_on_first_try_needs_no_retry():
    gen = PlateGenerator.__new__(PlateGenerator)
    gen.db = None
    gen.qwen = MagicMock()
    gen.qwen.edit_image = AsyncMock(return_value="https://img/a.png")
    gen.qwen.generate_image = AsyncMock()
    gen.oss = MagicMock()
    gen.oss.get_project_path = MagicMock(return_value="proj/plates/x.png")
    gen.oss.upload_bytes = MagicMock(return_value="https://oss/x.png")
    gen._fetch_bytes = MagicMock(return_value=b"good")
    ref = [1.0] + [0.0] * 511
    close = [0.5] + [(1 - 0.5**2) ** 0.5] + [0.0] * 510      # cosine 0.5 >= 0.35
    gen.embedder = MagicMock()
    gen.embedder.model = MagicMock()
    gen.embedder.model.embed = MagicMock(return_value=close)
    gen.embedder.extract = AsyncMock(return_value={"vector": close, "description": {}})

    await gen.generate_and_store_plate(
        project_id="p1", kind="character", key="Mia:uniform",
        prompt="same person, navy uniform",
        base_image_url="https://oss/face.png", match_vector=ref)
    gen.qwen.edit_image.assert_awaited_once()  # no wasted second image


@pytest.mark.asyncio
async def test_match_vector_from_pgvector_is_a_numpy_array():
    # face_vector loads from the DB as a numpy array — bool(array) raises
    # ("truth value of an array is ambiguous") and killed every verified plate
    import numpy as np
    gen = PlateGenerator.__new__(PlateGenerator)
    gen.db = None
    gen.qwen = MagicMock()
    gen.qwen.edit_image = AsyncMock(return_value="https://img/a.png")
    gen.qwen.generate_image = AsyncMock()
    gen.oss = MagicMock()
    gen.oss.get_project_path = MagicMock(return_value="proj/plates/x.png")
    gen.oss.upload_bytes = MagicMock(return_value="https://oss/x.png")
    gen._fetch_bytes = MagicMock(return_value=b"good")
    ref = np.array([1.0] + [0.0] * 511)
    close = [0.5] + [(1 - 0.5**2) ** 0.5] + [0.0] * 510
    gen.embedder = MagicMock()
    gen.embedder.model = MagicMock()
    gen.embedder.model.embed = MagicMock(return_value=close)
    gen.embedder.extract = AsyncMock(return_value={"vector": close, "description": {}})

    url, _ = await gen.generate_and_store_plate(
        project_id="p1", kind="character", key="Mia:uniform",
        prompt="same person, navy uniform",
        base_image_url="https://oss/face.png", match_vector=ref)
    assert url == "https://oss/x.png"
    gen.qwen.edit_image.assert_awaited_once()


def test_costume_plate_is_full_body_standing():
    # the plate standard: a fixed standing pose, face clearly visible, the
    # whole costume readable down to the shoes — never a scene performance
    from app.services.plate_generator import character_plate_prompt
    p = character_plate_prompt(True, "a woman around 20s", "navy sweater, jeans")
    assert "standing" in p
    assert "head to shoes" in p
    assert "waist-up" not in p


def test_outfit_scene_fluff_is_cleaned_from_the_plate():
    # the wardrobe text leaked scene context ("sitting by the window, staring
    # at the sea") and the model rendered the pose into the costume plate
    from app.services.plate_generator import character_plate_prompt
    p = character_plate_prompt(
        True, "a woman",
        "navy sweater and slim trousers, sitting by the window, staring at the sea")
    # the outfit clause of the prompt carries only wardrobe (the frame text
    # legitimately says 'Never sitting...' as an instruction)
    wearing = p.split("Wearing ", 1)[1].split(". Render")[0]
    assert "navy sweater" in wearing
    assert "sitting" not in wearing
    assert "window" not in wearing
    assert "sea" not in wearing


def test_negative_bans_sitting_not_full_body():
    from app.services.plate_generator import CHAR_PLATE_NEGATIVE
    assert "sitting" in CHAR_PLATE_NEGATIVE
    assert "full body" not in CHAR_PLATE_NEGATIVE


def test_eyewear_banned_unless_the_character_asks_for_it():
    from app.services.plate_generator import char_plate_negative, CHAR_PLATE_NEGATIVE
    # invented glasses were getting locked into seeded identities — ban by default
    assert "eyeglasses" in char_plate_negative("gentle gaze, refined jawline", "", None)
    # a character whose own description wears glasses keeps them
    assert char_plate_negative("always wears round glasses", "") == CHAR_PLATE_NEGATIVE
    # outfit-level eyewear (e.g. sunglasses from an outfit swap) also lifts the ban
    assert char_plate_negative("", "", "black suit with aviator sunglasses") == CHAR_PLATE_NEGATIVE


@pytest.mark.asyncio
async def test_face_reference_preflight_classifies_verdicts():
    """The upload-time probe: DataInspectionFailed (public figure) reads as
    rejected, a successful edit as ok, and any other failure as unknown so a
    flaky probe never blocks an upload."""
    from app.services.qwen_client import QwenClient
    client = QwenClient.__new__(QwenClient)

    client.edit_image = AsyncMock(side_effect=RuntimeError(
        'DashScope image-edit 400: {"code":"DataInspectionFailed"}'))
    assert await client.check_face_reference("https://oss/haaland.jpg") == "rejected"

    client.edit_image = AsyncMock(return_value="https://img/probe.png")
    assert await client.check_face_reference("https://oss/me.jpg") == "ok"

    client.edit_image = AsyncMock(side_effect=RuntimeError("timeout"))
    assert await client.check_face_reference("https://oss/me.jpg") == "unknown"
