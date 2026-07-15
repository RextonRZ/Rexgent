import uuid
import logging
from app.services.qwen_client import QwenClient
from app.services.oss_manager import OSSManager
from app.services.face_embedder import FaceEmbedder
from app.config import get_settings

logger = logging.getLogger(__name__)

# Fallback outfit when no wardrobe plan exists (never feed the face description in).
DEFAULT_OUTFIT = "a simple, well-fitted everyday outfit"

# Identity gate for face-referenced plates: raw ArcFace cosine at or above the
# genuine-pair threshold (same scale the continuity agent verifies with) counts
# as the same person. Below it, the render is re-rolled and the best attempt
# kept — one retry, so a stubborn miss costs at most one extra image.
IDENTITY_MATCH_SIM = 0.35
IDENTITY_MAX_ATTEMPTS = 2

import re as _re

# Image models love to invent spectacles onto "gentle/refined" faces, and an
# invented pair gets locked into the identity forever (the default plate seeds
# the face reference). Ban eyewear UNLESS the character's own description or
# outfit actually calls for it.
_EYEWEAR = _re.compile(r"glasses|spectacles|eyewear|sunglasses|眼镜", _re.I)


def char_plate_negative(*texts) -> str:
    if any(_EYEWEAR.search(x or "") for x in texts):
        return CHAR_PLATE_NEGATIVE
    return CHAR_PLATE_NEGATIVE + ", eyeglasses, spectacles, glasses on face"


# Keep the reference identity, one person only, and no scene bleed-through.
CHAR_PLATE_NEGATIVE = (
    "two people, second person, multiple people, another person, crowd, background people, "
    "different person, different face, altered facial features, distorted face, deformed, "
    # a plate is an identity + wardrobe reference, not a performance: a strong
    # expression on it bleeds into every shot that references the plate.
    "crying, tears, teary eyes, angry, frowning, scowling, grimacing, laughing, shouting, "
    "exaggerated expression, emotional expression, "
    "full body, wide shot, room interior, doorway, scene, busy background, cluttered, text, watermark"
)


def gender_bucket(gender: str | None) -> str | None:
    """Coarse male/female/unknown bucket from a free-text gender string, used to
    lead the face-plate subject phrase. (Not TTS — a plate needs to know whether
    to render 'a woman' vs 'a man' vs neither.)"""
    g = str(gender or "").lower()
    if any(w in g for w in ("female", "woman", "girl", "lady")):
        return "female"
    if any(w in g for w in ("male", "man", "boy", "guy")):
        return "male"
    return None


def subject_descriptor(gender: str | None = None, age: str | None = None,
                       appearance: str | None = None) -> str:
    """A concise 'who this is' phrase so plates stay CHARACTER-SPECIFIC even if the
    face-edit path can't run — otherwise two characters collapse into the same
    generic person. Uses gender/age/appearance, never the character's name (a name
    isn't visual). When gender is unknown (e.g. a pet or a child) we lean on the
    appearance so a dog stays a dog rather than becoming 'a person'."""
    b = gender_bucket(gender)
    lead = "a woman" if b == "female" else "a man" if b == "male" else ""
    # A numeric age ("20s") implies a human even when gender wasn't extracted —
    # dropping it let 'soft/delicate' face text read as a CHILD to the image model.
    if not lead and age and any(ch.isdigit() for ch in str(age)):
        lead = "a person"
    if lead and age:
        lead = f"{lead} around {age}"
    appearance = (appearance or "").strip()
    if len(appearance) > 220:  # keep the face from being drowned by a paragraph
        appearance = appearance[:220].rsplit(" ", 1)[0] + "…"
    if appearance:
        return f"{lead}, {appearance}" if lead else appearance
    return lead or "a person"


def character_plate_prompt(has_face: bool, subject: str, outfit: str = "") -> str:
    """A costume-plate prompt tuned for identity + a single subject: a waist-up studio
    shot (face stays large) of ONE subject on a plain backdrop. `subject` is who they
    are (gender/age/appearance). When `outfit` is empty we KEEP the reference's own
    clothing instead of imposing a generic outfit — so each character keeps their real
    look (and a dog/child isn't forced into an adult t-shirt)."""
    frame = ("Solo studio costume-reference photo of ONE subject alone, no other people, "
             "waist-up medium shot facing forward, neutral relaxed expression (calm and "
             "natural, mouth closed, not emoting), plain seamless neutral backdrop, "
             "soft even lighting. Ignore any location, action or scene — plain background only. "
             "This is an identity and wardrobe reference, not a performance — the emotion of "
             "each shot is set later at generation time.")
    outfit = (outfit or "").strip()
    if has_face:
        anchor = ("Keep the same age and body proportions as the reference — do not make "
                  "them younger or older.")
        if outfit:
            return (f"The exact same subject as the reference image ({subject}) — keep the "
                    f"identical face, and the same hair where the outfit does not cover it. "
                    f"{anchor} Wearing {outfit}. Render EVERY item of the outfit, including "
                    f"any headwear, eyewear and accessories. {frame}")
        # no story costume: preserve the reference's own clothing too
        return (f"The exact same subject as the reference image ({subject}) — keep the identical "
                f"face, hair and the same clothing as the reference. {anchor} {frame}")
    if outfit:
        return (f"{subject}, wearing {outfit}. Render every item of the outfit, "
                f"including any headwear and accessories. {frame}")
    return f"{subject}. {frame}"


class PlateGenerator:
    """Generates a reference plate (character costume, location, or style preset):
    Qwen image generation -> re-host on OSS -> (character only) ArcFace embedding.

    The generated image is downloaded ONCE; those bytes are both uploaded to OSS
    and (for character plates) fed to the face embedder — no second fetch.
    """

    def __init__(self, db=None):
        s = get_settings()
        self.qwen = QwenClient(s)
        self.oss = OSSManager(s)
        self.embedder = FaceEmbedder()
        self.db = db
        # after each generate_and_store_plate with a reference: True when the
        # face edit actually ran, False when every attempt fell back to
        # text-to-image (reference rejected), None when no reference was given
        self.last_face_preserved: bool | None = None

    @staticmethod
    def _fetch_bytes(url: str) -> bytes:
        import httpx
        return httpx.get(url, timeout=60.0).content

    async def _render_once(self, kind: str, key: str, prompt: str,
                           negative_prompt: str | None, base_image_url: str | None,
                           prompt_extend: bool) -> tuple[bytes, str]:
        """One render pass: face-edit when a reference exists (text-to-image as
        the degraded fallback), returns (image bytes, model used)."""
        image_model = "wan2.6-t2i"
        if base_image_url:
            try:
                raw_url = await self.qwen.edit_image(
                    prompt, base_image_url, negative_prompt=negative_prompt, prompt_extend=prompt_extend)
                image_model = "qwen-image-edit-max"
            except Exception as e:  # noqa: BLE001 — degrade gracefully to text-to-image
                logger.warning(
                    "edit_image failed for %s/%s (%s) — falling back to text-to-image; "
                    "the face will NOT be preserved for this plate.", kind, key, e)
                raw_url = await self.qwen.generate_image(
                    prompt=prompt, negative_prompt=negative_prompt, prompt_extend=prompt_extend)
        else:
            raw_url = await self.qwen.generate_image(
                prompt=prompt, negative_prompt=negative_prompt, prompt_extend=prompt_extend)
        return self._fetch_bytes(raw_url), image_model

    async def generate_and_store_plate(
        self, project_id: str, kind: str, key: str, prompt: str,
        style_ref: str | None = None, negative_prompt: str | None = None,
        base_image_url: str | None = None, prompt_extend: bool = True,
        match_vector: list | None = None,
    ) -> tuple[str, list | None]:
        """kind in {character, location, style}. Returns (oss_url, face_vector|None).

        When base_image_url is set (a character's face reference), the costume plate
        is generated by image-editing that face so the identity is preserved. With
        match_vector also set (the reference's ArcFace embedding), the generated
        face is VERIFIED against it: a below-threshold match re-rolls once and the
        closest attempt wins — the edit model drifts sometimes, and one cheap retry
        beats shipping a stranger in the character's costume."""
        from app.services.face_model import cosine_similarity
        # match_vector arrives as a numpy array when loaded from pgvector —
        # bool(array) raises, so test presence by length, never truthiness
        has_ref_vector = match_vector is not None and len(match_vector) > 0
        verify = bool(base_image_url) and has_ref_vector and kind == "character"
        attempts = IDENTITY_MAX_ATTEMPTS if verify else 1
        content: bytes | None = None
        best_sim = -1.0
        models_used: list[str] = []
        for attempt in range(attempts):
            rendered, image_model = await self._render_once(
                kind, key, prompt, negative_prompt, base_image_url, prompt_extend)
            models_used.append(image_model)
            if not verify:
                content = rendered
                break
            vec = self.embedder.model.embed(rendered)
            sim = cosine_similarity(match_vector, vec) if vec else 0.0
            if sim > best_sim:
                best_sim, content = sim, rendered
            if sim >= IDENTITY_MATCH_SIM:
                break
            logger.info("plate identity match %.2f below %.2f for %s/%s (attempt %d) — %s",
                        sim, IDENTITY_MATCH_SIM, kind, key, attempt + 1,
                        "retrying" if attempt + 1 < attempts else "keeping the closest attempt")
        # Surface the silent failure mode: a reference existed but every render
        # fell back to text-to-image (the edit model rejected the photo, e.g.
        # DataInspectionFailed on a recognizable public figure) — the shipped
        # face is NOT the uploaded one. Callers read this right after the call
        # to badge the plate instead of quietly showing a stranger.
        self.last_face_preserved = (
            any(m == "qwen-image-edit-max" for m in models_used)
            if base_image_url else None
        )
        # Unique filename per generation so a regenerated plate gets a NEW url — an
        # overwritten deterministic key returns the same url and the browser would
        # keep showing the cached (old) image.
        fname = f"{key.replace(':', '_')}_{uuid.uuid4().hex[:8]}.png"
        oss_key = self.oss.get_project_path(project_id, f"plates/{kind}", fname)
        oss_url = self.oss.upload_bytes(content, oss_key, content_type="image/png")

        if getattr(self, "db", None) is not None:
            from app.services.cost_ledger import record_image
            from collections import Counter
            for m, n in Counter(models_used).items():
                record_image(self.db, project_id, n, stage="casting", model=m)

        vector = None
        if kind == "character":
            result = await self.embedder.extract(image_bytes=content, image_url=oss_url)
            vector = result.get("vector")

        return oss_url, vector
