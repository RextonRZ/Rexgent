from app.services.qwen_client import QwenClient
from app.config import get_settings


class FaceEmbedder:
    def __init__(self):
        self.qwen = QwenClient(get_settings())

    async def extract_embedding(self, image_url: str) -> dict:
        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": (
                    "Describe the face of the main person in this image in detail. "
                    "Include: facial structure, eye shape, nose shape, jawline, skin tone, "
                    "hair style, hair color, distinctive features. "
                    "Return as JSON with keys: face_description (string), "
                    "distinctive_features (list of strings), "
                    "embedding_keywords (list of short visual keywords for video generation prompts). "
                    "Return ONLY the JSON."
                )},
            ],
        }]
        result = await self.qwen.chat_vision_json(messages=messages)
        if not isinstance(result, dict):
            return {"face_description": "", "distinctive_features": [], "embedding_keywords": []}
        return result

    async def compare_faces(self, stored_embedding: dict, frame_url: str) -> float:
        keywords = stored_embedding.get("embedding_keywords", [])
        keywords_str = ", ".join(keywords) if keywords else "the reference person"
        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": frame_url}},
                {"type": "text", "text": (
                    f"Compare the main person in this image to the following description: {keywords_str}. "
                    "Return JSON with keys: similarity_score (float 0.0-1.0), "
                    "matching_features (list), missing_features (list). "
                    "Return ONLY the JSON."
                )},
            ],
        }]
        result = await self.qwen.chat_vision_json(messages=messages)
        if not isinstance(result, dict):
            return 0.5
        try:
            return float(result.get("similarity_score", 0.5))
        except (TypeError, ValueError):
            return 0.5
