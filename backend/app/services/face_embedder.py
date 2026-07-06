from app.services.qwen_client import QwenClient
from app.services.face_model import get_face_model, cosine_similarity
from app.config import get_settings


class FaceEmbedder:
    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.model = get_face_model()

    async def extract(self, image_bytes: bytes, image_url: str) -> dict:
        """Real ArcFace vector + Qwen-VL text description.

        Returns: {"vector": list[float] | None, "description": dict}
        """
        vector = self.model.embed(image_bytes)

        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": (
                    "Describe the face of the main person: facial structure, eye shape, "
                    "jawline, skin tone, hair, distinctive features. Return JSON with keys "
                    "face_description (string) and embedding_keywords (list of short visual "
                    "keywords for video prompts). Return ONLY JSON."
                )},
            ],
        }]
        description = await self.qwen.chat_vision_json(messages=messages, task="face")
        if not isinstance(description, dict):
            description = {"face_description": "", "embedding_keywords": []}

        return {"vector": vector, "description": description}

    @staticmethod
    def compare_vectors(a: list[float], b: list[float]) -> float:
        return cosine_similarity(a, b)
