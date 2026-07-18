"""One-time generator for the create-drama picker sample images.

Renders one wan2.6-t2i sample per visual style (SAME subject in every style,
so the picker reads as "this exact scene, in your look") and one signature
still per genre. Files land in frontend/public/{styles,genres}/<key>.jpg as
small static assets — zero runtime cost after this script runs once.

Idempotent: existing files are skipped, so a moderation or network hiccup can
be retried by simply re-running.

    cd backend && python scripts/generate_picker_samples.py
"""
import asyncio
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from PIL import Image

from app.config import get_settings
from app.services.qwen_client import QwenClient
from app.services.style_catalog import STYLE_SEEDS

FRONTEND_PUBLIC = Path(__file__).resolve().parents[2] / "frontend" / "public"

# every style renders THIS scene, so flipping through cards shows the look
# changing around an identical moment
STYLE_SUBJECT = ("a teenage girl gently holding a small white rabbit, "
                 "standing in a sunlit bedroom, warm afternoon light, "
                 "medium shot, no text")

GENRE_PROMPTS = {
    "romance": "two young lovers sharing one umbrella under falling cherry blossoms at dusk",
    "drama": "a tense family confrontation across a dinner table, moody window light",
    "comedy": "a young man mid pratfall in a bright kitchen, a cloud of flour in the air",
    "horror": "a dark hallway with a distant silhouetted figure under a flickering light",
    "thriller": "a woman glancing over her shoulder on a rainy neon street at night",
    "mystery": "a detective desk covered in case photos and string under a single lamp",
    "sci-fi": "a lone figure dwarfed by a vast glowing spaceship inside a hangar",
    "fantasy": "a cloaked traveler gazing up at a floating castle at golden hour",
    "action": "a runner leaping between rooftops at sunset, dynamic motion",
    "slice of life": "friends laughing around a small noodle shop table, warm evening light",
    "historical": "a lantern lit palace courtyard with figures in traditional dress",
    "melodrama": "a tearful farewell on a rainy train platform, umbrellas and mist",
}

NEGATIVE = "text, watermark, caption, letters, logo, subtitles"


def _slug(key: str) -> str:
    return key.replace(" ", "-")


async def _render(qwen: QwenClient, sem: asyncio.Semaphore, prompt: str,
                  dest: Path) -> None:
    if dest.exists():
        print(f"  skip (exists)  {dest.name}")
        return
    async with sem:
        try:
            url = await qwen.generate_image(prompt, negative_prompt=NEGATIVE,
                                            size="1280*720")
            async with httpx.AsyncClient() as http:
                r = await http.get(url, timeout=60.0)
                r.raise_for_status()
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
            img.thumbnail((512, 512))
            dest.parent.mkdir(parents=True, exist_ok=True)
            img.save(dest, "JPEG", quality=85, optimize=True)
            print(f"  ok             {dest.name}")
        except Exception as e:  # noqa: BLE001 — report and continue; rerun retries
            print(f"  FAILED         {dest.name}: {str(e)[:160]}")


async def main() -> None:
    qwen = QwenClient(get_settings())
    sem = asyncio.Semaphore(4)
    jobs = []

    styles_dir = FRONTEND_PUBLIC / "styles"
    print(f"styles -> {styles_dir}")
    jobs.append(_render(
        qwen, sem,
        f"cinematic realistic drama film still, photoreal, {STYLE_SUBJECT}",
        styles_dir / "photoreal.jpg"))
    for key, seed in STYLE_SEEDS.items():
        jobs.append(_render(qwen, sem, f"{seed}, {STYLE_SUBJECT}",
                            styles_dir / f"{_slug(key)}.jpg"))

    genres_dir = FRONTEND_PUBLIC / "genres"
    print(f"genres -> {genres_dir}")
    for key, scene in GENRE_PROMPTS.items():
        jobs.append(_render(
            qwen, sem,
            f"cinematic film still, {scene}, rich color grading, no text",
            genres_dir / f"{_slug(key)}.jpg"))

    await asyncio.gather(*jobs)
    print("done")


if __name__ == "__main__":
    asyncio.run(main())
