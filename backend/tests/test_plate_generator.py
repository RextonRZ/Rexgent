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
