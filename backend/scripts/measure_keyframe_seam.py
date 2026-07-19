"""MEASUREMENT GATE (Task 2.5, keyframe-first-identity plan) — spends real
render credit, run manually by the controller, never by an agent.

Picks a real character with a locked ArcFace face_vector and a default
costume plate, renders ONE keyframe still against that plate (+ a location
plate if the project has one), then dispatches ONE HappyHorse i2v clip from
that keyframe and ONE HappyHorse r2v clip from the same plate stack. Every
frame that matters is pulled and embedded, and five cosine-similarity
numbers are printed:

    kf_still_vs_vector     - does the keyframe still even look like them
    i2v_first_vs_vector    - does i2v's own first frame inherit the face
    i2v_last_vs_vector     - M2, motion retention: does the face survive 5s
    r2v_last_vs_vector     - the baseline r2v path's last-frame identity
    i2v_last_vs_r2v_last   - M1, the SEAM: do the two paths land on the
                              same face, or does keyframe-first drift away
                              from what r2v alone would have produced

Every extracted frame is saved under scripts/seam_check/ next to this file
so the controller can eyeball them, not just read the numbers.

Run from backend/:  python scripts/measure_keyframe_seam.py
"""
import asyncio
import os
import sys

import httpx
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import get_settings  # noqa: E402
from app.services.face_model import cosine_similarity, get_face_model  # noqa: E402
from app.services.frame_sampler import extract_first_frame, extract_last_frame  # noqa: E402
from app.services.keyframe import render_keyframe  # noqa: E402
from app.services.plate_generator import IDENTITY_MATCH_SIM  # noqa: E402
from app.services.qwen_client import QwenClient  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(__file__), "seam_check")

# a simple silent beat - no dialogue, no complex action, so any identity
# drift measured here is the pipeline's, not the prompt's
BEAT_PROMPT = ("standing by the garden gate, turning slightly, soft "
              "afternoon light")

# app.config.get_settings().database_url already defaults to this; kept as
# an explicit fallback per the plan in case settings ever return empty
_FALLBACK_DB_URL = "postgresql://rexgent:rexgent_dev@localhost:5432/rexgent"


def _parse_vector(raw) -> list[float] | None:
    """characters.face_vector is a pgvector column; over a raw (non-ORM)
    connection with no vector adapter registered, psycopg2 hands it back as
    the literal "[0.01,-0.02,...]" text Postgres prints it as. Handle a
    plain list too in case a future driver registers the type itself."""
    if raw is None:
        return None
    if isinstance(raw, str):
        s = raw.strip().strip("[]")
        return [float(x) for x in s.split(",")] if s else None
    return list(raw)


def _fetch_case() -> dict | None:
    """The latest project with a character carrying BOTH a locked
    face_vector and a default costume plate, plus that project's ratio and
    one location plate if it has any (raw SQL join - no ORM session needed
    for a one-shot measurement script)."""
    settings = get_settings()
    db_url = getattr(settings, "database_url", None) or _FALLBACK_DB_URL
    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT c.id AS character_id,
                       c.name AS character_name,
                       c.face_vector AS face_vector,
                       c.project_id AS project_id,
                       cv.plate_image_url AS plate_image_url,
                       p.video_ratio AS video_ratio
                FROM characters c
                JOIN costume_variants cv ON cv.character_id = c.id
                JOIN projects p ON p.id = c.project_id
                WHERE cv.is_default IS TRUE
                  AND cv.plate_image_url IS NOT NULL
                  AND c.face_vector IS NOT NULL
                  -- PHOTOREAL only: ArcFace is meaningless on stylized faces,
                  -- and the keyframe route excludes stylized dramas anyway —
                  -- measuring the seam on an anime face measures nothing
                  AND p.visual_style IS NULL
                ORDER BY p.created_at DESC
                LIMIT 1
            """)).mappings().first()
            if row is None:
                return None
            case = dict(row)
            loc = conn.execute(text("""
                SELECT plate_image_url FROM location_plates
                WHERE project_id = :pid AND plate_image_url IS NOT NULL
                LIMIT 1
            """), {"pid": case["project_id"]}).first()
            case["location_plate_url"] = loc[0] if loc else None
        return case
    finally:
        engine.dispose()


def _save(name: str, data: bytes | None) -> None:
    if not data:
        return
    with open(os.path.join(OUT_DIR, name), "wb") as f:
        f.write(data)


def _embed(data: bytes | None) -> list[float] | None:
    if not data:
        return None
    return get_face_model().embed(data)


def _print_score(label: str, emb, other) -> None:
    if emb is None or other is None:
        print(f"{label}: NO FACE")
        return
    print(f"{label}: {cosine_similarity(emb, other):.4f}")


async def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    case = _fetch_case()
    if case is None:
        print("BLOCKED: no character with a face_vector + default costume "
              "plate found in the DB - cannot run the seam measurement.")
        return

    face_vector = _parse_vector(case["face_vector"])
    plate_url = case["plate_image_url"]
    location_url = case.get("location_plate_url")
    ratio = case.get("video_ratio") or "9:16"
    ref_urls = [plate_url] + ([location_url] if location_url else [])

    print(f"character: {case['character_name']} ({case['character_id']})")
    print(f"project:   {case['project_id']}  ratio={ratio}")
    print(f"plate:     {plate_url}")
    print(f"location:  {location_url}")
    print(f"IDENTITY_MATCH_SIM (app.services.plate_generator) = {IDENTITY_MATCH_SIM}")
    print()

    qwen = QwenClient(get_settings())

    # --- 1. render + verify the keyframe still --------------------------
    print("rendering keyframe...")
    kf_url, kf_internal_score, kf_attempts = await render_keyframe(
        qwen=qwen, prompt=BEAT_PROMPT, ref_urls=ref_urls, ratio=ratio,
        face_vector=face_vector, stylized=False, threshold=IDENTITY_MATCH_SIM)
    print(f"keyframe: url={kf_url} internal_score={kf_internal_score} "
          f"attempts={kf_attempts}")
    if not kf_url:
        print("BLOCKED: keyframe render failed outright - aborting before "
              "any video spend.")
        return

    async with httpx.AsyncClient() as http:
        kf_bytes = (await http.get(kf_url, timeout=120)).content
    _save("keyframe.jpg", kf_bytes)
    kf_emb = _embed(kf_bytes)

    # --- 2. dispatch i2v (from the keyframe) and r2v (from the plates) --
    i2v_media = [{"type": "first_frame", "url": kf_url}]
    r2v_media = [{"type": "reference_image", "url": plate_url}]
    if location_url:
        r2v_media.append({"type": "reference_image", "url": location_url})

    print("dispatching i2v + r2v clips...")
    i2v_task = await qwen.generate_video_happyhorse(
        prompt=BEAT_PROMPT, duration=5, mode="i2v",
        reference_media=i2v_media, ratio=ratio)
    r2v_task = await qwen.generate_video_happyhorse(
        prompt=BEAT_PROMPT, duration=5, mode="r2v",
        reference_media=r2v_media, ratio=ratio)
    print(f"i2v task_id={i2v_task}  r2v task_id={r2v_task}")

    print("polling (up to 900s each, concurrently)...")
    i2v_clip_url, r2v_clip_url = await asyncio.gather(
        qwen.poll_video_task(i2v_task, timeout=900),
        qwen.poll_video_task(r2v_task, timeout=900))
    print(f"i2v clip: {i2v_clip_url}")
    print(f"r2v clip: {r2v_clip_url}")

    # --- 3. extract + save frames ----------------------------------------
    i2v_first = extract_first_frame(i2v_clip_url)
    i2v_last = extract_last_frame(i2v_clip_url)
    r2v_last = extract_last_frame(r2v_clip_url)
    _save("i2v_first.jpg", i2v_first)
    _save("i2v_last.jpg", i2v_last)
    _save("r2v_last.jpg", r2v_last)

    i2v_first_emb = _embed(i2v_first)
    i2v_last_emb = _embed(i2v_last)
    r2v_last_emb = _embed(r2v_last)

    # --- 4. the five gate numbers -----------------------------------------
    print()
    print("=== seam / motion-retention scores ===")
    _print_score("kf_still_vs_vector", kf_emb, face_vector)
    _print_score("i2v_first_vs_vector", i2v_first_emb, face_vector)
    _print_score("i2v_last_vs_vector", i2v_last_emb, face_vector)
    _print_score("r2v_last_vs_vector", r2v_last_emb, face_vector)
    _print_score("i2v_last_vs_r2v_last", i2v_last_emb, r2v_last_emb)
    print()
    print(f"IDENTITY_MATCH_SIM threshold for reference: {IDENTITY_MATCH_SIM}")
    print(f"frames saved under: {OUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
