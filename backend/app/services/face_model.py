import io
import logging
from typing import Protocol
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 512  # ArcFace buffalo_l output dim


def cosine_similarity(a: list[float], b: list[float]) -> float:
    # a/b may be numpy arrays (from pgvector) or lists; avoid bool(array).
    if a is None or b is None or len(a) == 0 or len(b) == 0 or len(a) != len(b):
        return 0.0
    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0.0:
        return 0.0
    return float(np.dot(va, vb) / denom)


class FaceEmbeddingModel(Protocol):
    def embed(self, image_bytes: bytes) -> list[float] | None:
        """Return a face embedding vector, or None if no face detected."""
        ...

    def embed_all(self, image_bytes: bytes) -> list[list[float]]:
        """Every detected face's embedding (empty list when none)."""
        ...


class InsightFaceModel:
    """ArcFace (buffalo_l) embeddings via InsightFace. 512-dim normalised vectors."""

    def __init__(self):
        from insightface.app import FaceAnalysis

        self._app = FaceAnalysis(
            name="buffalo_l", providers=["CPUExecutionProvider"]
        )
        self._app.prepare(ctx_id=-1, det_size=(640, 640))

    def _detect(self, image_bytes: bytes):
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        arr = np.array(img)[:, :, ::-1]  # RGB -> BGR for insightface
        return self._app.get(arr)

    def embed(self, image_bytes: bytes) -> list[float] | None:
        faces = self._detect(image_bytes)
        if not faces:
            return None
        # Largest face by bbox area.
        face = max(
            faces,
            key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
        )
        return face.normed_embedding.tolist()

    def embed_all(self, image_bytes: bytes) -> list[list[float]]:
        return [f.normed_embedding.tolist() for f in self._detect(image_bytes)]


_model: FaceEmbeddingModel | None = None


def get_face_model() -> FaceEmbeddingModel:
    global _model
    if _model is None:
        _model = InsightFaceModel()
    return _model
