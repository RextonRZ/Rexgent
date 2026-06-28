from app.services.face_embedder import FaceEmbedder


class ConsistencyGuard:
    def __init__(self):
        self.face_embedder = FaceEmbedder()

    async def validate(
        self,
        frame_urls: list[str],
        expected_characters: list[dict],
        threshold: float = 0.75,
    ) -> dict:
        character_results = []

        for char in expected_characters:
            scores = []
            for frame_url in frame_urls:
                score = await self.face_embedder.compare_faces(
                    stored_embedding=char.get("face_embedding") or {},
                    frame_url=frame_url,
                )
                scores.append(score)

            avg_score = sum(scores) / len(scores) if scores else 0.0
            passed = avg_score >= threshold

            character_results.append({
                "character_name": char.get("name", "Unknown"),
                "detected": True,
                "similarity_score": round(avg_score, 3),
                "pass": passed,
                "frame_scores": [round(s, 3) for s in scores],
                "failure_reason": None if passed else f"Average similarity {avg_score:.2f} below threshold {threshold}",
            })

        overall_pass = all(cr["pass"] for cr in character_results) if character_results else True
        overall_similarity = (
            sum(cr["similarity_score"] for cr in character_results) / len(character_results)
            if character_results else 1.0
        )

        recommendation = "APPROVE"
        retry_instruction = None
        if not overall_pass:
            min_score = min(cr["similarity_score"] for cr in character_results)
            if min_score >= 0.6:
                recommendation = "RETRY_STRONGER_FACE"
                retry_instruction = "Add more face keywords to prompt. Use subject reference image."
            elif min_score >= 0.4:
                recommendation = "RETRY_SAME_PROMPT"
                retry_instruction = "Reseed generation with different random seed."
            else:
                recommendation = "MANUAL_REVIEW"
                retry_instruction = "Embedding mismatch too large. Manual review required."

        return {
            "overall_pass": overall_pass,
            "overall_similarity": round(overall_similarity, 3),
            "character_results": character_results,
            "recommendation": recommendation,
            "retry_instruction": retry_instruction,
        }
