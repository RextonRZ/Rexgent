import base64
from app.services.face_embedder import FaceEmbedder
from app.services.frame_sampler import sample_frames
from app.services.qwen_client import QwenClient
from app.config import get_settings


class ConsistencyGuard:
    def __init__(self):
        self.embedder = FaceEmbedder()
        self.qwen = QwenClient(get_settings())

    def _sample(self, clip_url: str, duration: float) -> list[bytes]:
        return sample_frames(clip_url, duration, count=3)

    async def validate(
        self,
        clip_url: str,
        duration: float,
        expected_characters: list[dict],
        threshold: float = 0.6,
    ) -> dict:
        frames = self._sample(clip_url, duration)
        character_results = []

        for char in expected_characters:
            ref_vec = char.get("face_vector")
            if not ref_vec:
                character_results.append({
                    "character_name": char.get("name", "Unknown"),
                    "detected": False,
                    "similarity_score": None,
                    "pass": True,  # cannot verify -> do not block, but flag
                    "frame_scores": [],
                    "failure_reason": "No reference vector — appearance unverifiable",
                })
                continue

            scores = []
            for frame in frames:
                frame_vec = self.embedder.model.embed(frame)
                if frame_vec is None:
                    continue
                scores.append(self.embedder.compare_vectors(ref_vec, frame_vec))

            avg = sum(scores) / len(scores) if scores else 0.0
            passed = avg >= threshold
            character_results.append({
                "character_name": char.get("name", "Unknown"),
                "detected": len(scores) > 0,
                "similarity_score": round(avg, 3),
                "pass": passed,
                "frame_scores": [round(s, 3) for s in scores],
                "failure_reason": None if passed else f"Cosine {avg:.2f} < {threshold}",
            })

        verifiable = [c for c in character_results if c["similarity_score"] is not None]
        overall_pass = all(c["pass"] for c in verifiable) if verifiable else True
        overall_similarity = (
            sum(c["similarity_score"] for c in verifiable) / len(verifiable)
            if verifiable else 1.0
        )

        diagnosis = None
        retry_instruction = None
        recommendation = "APPROVE"
        if not overall_pass and frames:
            diagnosis = await self._diagnose(frames[len(frames) // 2], expected_characters)
            retry_instruction = diagnosis.get(
                "suggested_change", "Reseed and emphasise facial features."
            )
            recommendation = "RETRY_TARGETED"

        return {
            "overall_pass": overall_pass,
            "overall_similarity": round(overall_similarity, 3),
            "character_results": character_results,
            "recommendation": recommendation,
            "diagnosis": diagnosis,
            "retry_instruction": retry_instruction,
        }

    async def _diagnose(self, frame_bytes: bytes, expected_characters: list[dict]) -> dict:
        """Ask Qwen-VL WHY the face didn't match and what to change (Fix #6)."""
        b64 = base64.b64encode(frame_bytes).decode()
        names = ", ".join(c.get("name", "?") for c in expected_characters)
        keywords: list[str] = []
        for c in expected_characters:
            keywords += (c.get("description") or {}).get("embedding_keywords", [])
        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": (
                    f"This frame should show character(s): {names}, who look like: "
                    f"{', '.join(keywords) or 'the reference'}. The generated face does NOT match. "
                    "Diagnose the single most likely VISUAL reason (lighting, angle, hairstyle, "
                    "age, ethnicity drift, occlusion) and give ONE specific prompt change to fix it. "
                    'Return JSON: {"reason": string, "suggested_change": string}. Return ONLY JSON.'
                )},
            ],
        }]
        result = await self.qwen.chat_vision_json(messages=messages)
        if not isinstance(result, dict):
            return {"reason": "unknown", "suggested_change": "Reseed and emphasise facial features."}
        return result
