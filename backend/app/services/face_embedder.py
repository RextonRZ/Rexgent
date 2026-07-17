import logging

from app.services.face_model import get_face_model, cosine_similarity
from app.config import get_settings

logger = logging.getLogger(__name__)


class FaceEmbedder:
    def __init__(self):
        # ONLY the local ArcFace model. The identity vector — what actually
        # locks a character's face across every shot — is computed offline and
        # must NOT depend on a Qwen key: constructing a QwenClient here used to
        # raise on a bring-your-own-key deploy with no key in context, which
        # killed the whole embedding (vector included) and left faces unlocked.
        self.model = get_face_model()

    async def extract(self, image_bytes: bytes, image_url: str) -> dict:
        """Real ArcFace vector (identity lock) + a best-effort Qwen-VL text
        description. The vector always computes; the description degrades to
        empty if the vision call is unavailable, so a missing key or a flaky
        VL response can never cost you the face lock.

        Returns: {"vector": list[float] | None, "description": dict}
        """
        vector = self.model.embed(image_bytes)

        description = {"face_description": "", "embedding_keywords": []}
        try:
            from app.services.qwen_client import QwenClient
            messages = [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": (
                        "Describe the face of the main person: facial structure, eye shape, "
                        "jawline, skin tone, hair (exact length, style and colour), facial "
                        "hair (state it exactly if present), and EYEWEAR — if they wear "
                        "glasses, name the exact pair ('thin black rectangular glasses'); "
                        "if they wear none, write NOTHING about eyewear (never 'no "
                        "glasses'). Then any distinctive features. Return JSON with keys "
                        "face_description (string) and embedding_keywords (list of short visual "
                        "keywords for video prompts). Return ONLY JSON."
                    )},
                ],
            }]
            desc = await QwenClient(get_settings()).chat_vision_json(
                messages=messages, task="face")
            if isinstance(desc, dict):
                description = desc
        except Exception as e:  # noqa: BLE001 — the vector is what matters
            logger.warning("face description skipped (vector still locked): %s", e)

        return {"vector": vector, "description": description}

    @staticmethod
    def compare_vectors(a: list[float], b: list[float]) -> float:
        return cosine_similarity(a, b)
