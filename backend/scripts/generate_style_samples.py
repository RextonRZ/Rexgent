"""One sample video per visual style for the landing reel: the SAME scene
(the girl reaching toward the white rabbit at the rusty garden gate), the
SAME two reference images (a real face for the girl, a real rabbit), the
SAME prompt — only the style seed changes. Photoreal included.

Resume-safe: styles whose mp4 already exists under frontend/public/
style-samples/ are skipped, so a crashed or stopped run just reruns.

Run from backend/:  python scripts/generate_style_samples.py
"""
import asyncio
import json
import os
import sys

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import get_settings  # noqa: E402
from app.services.oss_manager import OSSManager  # noqa: E402
from app.services.qwen_client import QwenClient  # noqa: E402
from app.services.style_catalog import STYLE_SEEDS  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..",
                       "frontend", "public", "style-samples")
STATE_PATH = os.path.join(os.path.dirname(__file__), "style_samples_state.json")
FACE_REF_LOCAL = os.path.join(os.path.dirname(__file__), "..", "..",
                              "frontend", "public", "refimg.png")

# the drama's signature moment, style-agnostic wording; the style seed is
# appended per sample and is the ONLY thing that changes
BASE_PROMPT = (
    "A ten year old girl with dark braided hair and a red hairband, wearing a "
    "blue dress with a white apron, kneels beside a rusty iron garden gate "
    "covered in ivy and gently reaches toward a small white rabbit with a red "
    "collar sitting on the gravel path. The girl's face matches the reference "
    "person exactly; the rabbit matches the reference rabbit exactly. Warm "
    "afternoon light, soft shadows, one slow gentle camera push in. Ambient "
    "garden sound, no dialogue, no music. Duration: 5 seconds."
)
NEGATIVE = ("text, words, subtitles, watermark, logo, extra person, "
            "duplicate person, deformed hands, giant rabbit")

PHOTOREAL_SEED = ("photorealistic live action cinematic film still, natural "
                  "skin texture, shallow depth of field, filmic color grade")

CONCURRENCY = 3


def _state() -> dict:
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(st: dict) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


async def ensure_refs(qwen: QwenClient, oss: OSSManager, st: dict) -> tuple[str, str]:
    """Face ref: the landing demo face uploaded to our OSS. Rabbit ref:
    generated once photoreal, re-hosted on our OSS (dashscope URLs expire)."""
    if not st.get("face_url"):
        with open(FACE_REF_LOCAL, "rb") as f:
            data = f.read()
        st["face_url"] = oss.upload_bytes(
            data, "landing/style-samples/face_ref.png", content_type="image/png")
        _save_state(st)
        print("face ref uploaded:", st["face_url"][:80])
    if not st.get("rabbit_url"):
        tmp = await qwen.generate_image(
            "studio photograph of one real small white rabbit wearing a thin "
            "red collar, sitting, full body, plain light background, sharp "
            "focus, natural fur detail",
            negative_prompt="cartoon, illustration, drawing, text, watermark",
            size="1280*1280")
        async with httpx.AsyncClient(timeout=120) as h:
            img = (await h.get(tmp)).content
        st["rabbit_url"] = oss.upload_bytes(
            img, "landing/style-samples/rabbit_ref.jpg", content_type="image/jpeg")
        _save_state(st)
        print("rabbit ref generated:", st["rabbit_url"][:80])
    return st["face_url"], st["rabbit_url"]


async def render_style(qwen: QwenClient, sem: asyncio.Semaphore, key: str,
                       seed_text: str, face_url: str, rabbit_url: str) -> None:
    dest = os.path.join(OUT_DIR, f"{key}.mp4")
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        print(f"[skip] {key} (exists)")
        return
    async with sem:
        prompt = f"{seed_text}. {BASE_PROMPT}"
        try:
            task = await qwen.generate_video_happyhorse(
                prompt=prompt, duration=5, mode="r2v",
                reference_media=[
                    {"type": "reference_image", "url": face_url},
                    {"type": "reference_image", "url": rabbit_url},
                ],
                ratio="16:9", negative_prompt=NEGATIVE)
            print(f"[submitted] {key}")
            url = await qwen.poll_video_task(task, timeout=900)
            async with httpx.AsyncClient(timeout=300) as h:
                data = (await h.get(url)).content
            with open(dest, "wb") as f:
                f.write(data)
            print(f"[done] {key} ({len(data) // 1024} KB)")
        except Exception as e:  # noqa: BLE001 — one style failing must not kill the batch
            print(f"[FAILED] {key}: {e}")


async def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    qwen = QwenClient(get_settings())
    oss = OSSManager(get_settings())
    st = _state()
    face_url, rabbit_url = await ensure_refs(qwen, oss, st)

    styles: list[tuple[str, str]] = [("photoreal", PHOTOREAL_SEED)]
    styles += list(STYLE_SEEDS.items())
    sem = asyncio.Semaphore(CONCURRENCY)
    await asyncio.gather(*(render_style(qwen, sem, k, s, face_url, rabbit_url)
                           for k, s in styles))
    have = [f for f in os.listdir(OUT_DIR) if f.endswith(".mp4")]
    print(f"finished: {len(have)}/{len(styles)} samples in {OUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
