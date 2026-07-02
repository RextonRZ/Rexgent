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
