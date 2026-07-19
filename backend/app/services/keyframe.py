"""Keyframe-first identity: the shot's OPENING FRAME drawn as a still by the
image model (which holds faces far better than video models) against the
cast's plates, ArcFace-verified, then animated by i2v. A bad keyframe costs
an image retry; a bad video costs a clip — verify before the expensive step.
Inspired by drama916's stills-first pipeline; the verification gate is ours."""
import logging

import httpx

logger = logging.getLogger(__name__)

_SIZES = {"9:16": "1080*1920", "16:9": "1920*1080"}
KEYFRAME_RETRIES = 2   # re-rolls after the first sub-threshold attempt


def size_for_ratio(ratio) -> str:
    return _SIZES.get(str(ratio or ""), "1280*1280")


async def _face_score(image_url: str, face_vector) -> float | None:
    """ArcFace similarity of the keyframe's face to the locked identity."""
    from app.services.face_model import cosine_similarity, get_face_model
    async with httpx.AsyncClient() as http:
        data = (await http.get(image_url, timeout=120)).content
    emb = get_face_model().embed(data)
    if not emb:
        return None
    return cosine_similarity(emb, list(face_vector))


async def _rehost(image_url: str) -> str:
    """Dashscope URLs expire — copy the winner to our OSS."""
    import uuid

    from app.config import get_settings
    from app.services.oss_manager import OSSManager
    async with httpx.AsyncClient() as http:
        data = (await http.get(image_url, timeout=120)).content
    oss = OSSManager(get_settings())
    key = f"keyframes/kf_{uuid.uuid4().hex[:12]}.png"
    return oss.upload_bytes(data, key, content_type="image/png")


async def render_keyframe(*, qwen, prompt: str, ref_urls: list[str], ratio,
                          face_vector, stylized: bool, threshold: float
                          ) -> tuple[str | None, float | None, int]:
    """(oss_url, score, attempts_used) for a verified keyframe still, or
    (None, None, attempts_used) on total failure — the caller falls back to
    r2v, never raises, and bills EXACTLY attempts_used images (cost guard
    C1). Verification is skipped for vectorless identities; stylized dramas
    never reach this service (the runner's verified-only gate)."""
    kf_prompt = ("The opening frame of this shot as ONE cinematic still. "
                 "Keep the EXACT same faces, hair and outfits as the "
                 "reference images - same people, same look. " + str(prompt))
    verify = bool(face_vector) and not stylized
    best_url, best_score = None, None
    max_attempts = 1 + (KEYFRAME_RETRIES if verify else 0)
    used = 0
    try:
        for _ in range(max_attempts):
            used += 1
            url = await qwen.generate_image_with_refs(
                kf_prompt, list(ref_urls or []), size=size_for_ratio(ratio))
            if not verify:
                return await _rehost(url), None, used
            score = await _face_score(url, face_vector)
            if score is not None and (best_score is None or score > best_score):
                best_url, best_score = url, score
            if score is not None and score >= threshold:
                break
        if best_url is None:
            return None, None, used
        return await _rehost(best_url), best_score, used
    except Exception as e:  # noqa: BLE001 — keyframes are an upgrade, never a blocker
        logger.warning("keyframe render failed, falling back to r2v: %s", e)
        return None, None, max(1, used)
