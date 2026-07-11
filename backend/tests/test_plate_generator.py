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


@pytest.mark.asyncio
async def test_character_plate_falls_back_to_text_when_edit_fails():
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
    assert url == "https://oss/x.png"
    gen.qwen.generate_image.assert_awaited_once()  # fell back


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


def test_eyewear_banned_unless_the_character_asks_for_it():
    from app.services.plate_generator import char_plate_negative, CHAR_PLATE_NEGATIVE
    # invented glasses were getting locked into seeded identities — ban by default
    assert "eyeglasses" in char_plate_negative("gentle gaze, refined jawline", "", None)
    # a character whose own description wears glasses keeps them
    assert char_plate_negative("always wears round glasses", "") == CHAR_PLATE_NEGATIVE
    # outfit-level eyewear (e.g. sunglasses from an outfit swap) also lifts the ban
    assert char_plate_negative("", "", "black suit with aviator sunglasses") == CHAR_PLATE_NEGATIVE
