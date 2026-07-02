from app.services.qwen_client import QwenClient
from app.services.oss_manager import OSSManager
from app.services.face_embedder import FaceEmbedder
from app.config import get_settings


class PlateGenerator:
    """Generates a reference plate (character costume, location, or style preset):
    Qwen image generation -> re-host on OSS -> (character only) ArcFace embedding.

    The generated image is downloaded ONCE; those bytes are both uploaded to OSS
    and (for character plates) fed to the face embedder — no second fetch.
    """

    def __init__(self):
        s = get_settings()
        self.qwen = QwenClient(s)
        self.oss = OSSManager(s)
        self.embedder = FaceEmbedder()

    @staticmethod
    def _fetch_bytes(url: str) -> bytes:
        import httpx
        return httpx.get(url, timeout=60.0).content

    async def generate_and_store_plate(
        self, project_id: str, kind: str, key: str, prompt: str,
        style_ref: str | None = None, negative_prompt: str | None = None,
    ) -> tuple[str, list | None]:
        """kind in {character, location, style}. Returns (oss_url, face_vector|None)."""
        raw_url = await self.qwen.generate_image(prompt=prompt, negative_prompt=negative_prompt)
        content = self._fetch_bytes(raw_url)
        oss_key = self.oss.get_project_path(project_id, f"plates/{kind}", f"{key.replace(':', '_')}.png")
        oss_url = self.oss.upload_bytes(content, oss_key, content_type="image/png")

        vector = None
        if kind == "character":
            result = await self.embedder.extract(image_bytes=content, image_url=oss_url)
            vector = result.get("vector")

        return oss_url, vector
