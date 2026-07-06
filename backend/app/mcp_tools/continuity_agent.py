import base64
from app.services.face_embedder import FaceEmbedder
from app.services.frame_sampler import sample_frames
from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.config import get_settings
from app.services.wardrobe_planner import map_variant_for_scene

FACE_W, OUTFIT_W, BG_W = 0.5, 0.25, 0.25
PASS_THRESHOLD = 55   # 0-100


def combine_scores(face, outfit, background) -> int:
    parts, weights = [], []
    if face is not None:
        parts.append(face); weights.append(FACE_W)
    if outfit is not None:
        parts.append(outfit); weights.append(OUTFIT_W)
    if background is not None:
        parts.append(background); weights.append(BG_W)
    if not parts:
        return 100
    score = sum(p * w for p, w in zip(parts, weights)) / sum(weights)
    return round(score * 100)


class ContinuityAgent:
    def __init__(self):
        s = get_settings()
        self.embedder = FaceEmbedder()
        self.qwen = QwenClient(s)
        self.vl_prompt = load_prompt("continuity_vl.txt")
        self.vl_model = s.qwen_vl_continuity_model

    def _sample(self, clip_url, duration):
        return sample_frames(clip_url, duration, count=3)

    async def validate(self, clip_url, duration, characters_in_frame, bible, scene_number) -> dict:
        frames = self._sample(clip_url, duration)
        # face
        face_scores = []
        for name in characters_in_frame:
            ch = bible["characters"].get(name)
            if not ch:
                continue
            v = map_variant_for_scene(ch.get("variants", []), scene_number)
            ref = (v or {}).get("face_vector")
            if not ref:
                continue
            for fr in frames:
                fv = self.embedder.model.embed(fr)
                if fv is not None:
                    face_scores.append(self.embedder.compare_vectors(ref, fv))
        face = sum(face_scores) / len(face_scores) if face_scores else None
        # outfit + background via one VL call on the middle frame
        outfit = background = None
        if frames:
            mid = frames[len(frames) // 2]
            b64 = base64.b64encode(mid).decode()
            char_plate = next((map_variant_for_scene(bible["characters"][n].get("variants", []), scene_number)
                               for n in characters_in_frame if n in bible["characters"]), None)
            loc_plate = (bible.get("location_by_scene") or {}).get(scene_number)
            content = [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                       {"type": "text", "text": self.vl_prompt}]
            if char_plate and char_plate.get("plate_image_url"):
                content.append({"type": "image_url", "image_url": {"url": char_plate["plate_image_url"]}})
            if loc_plate:
                content.append({"type": "image_url", "image_url": {"url": loc_plate}})
            vl = await self.qwen.chat_vision_json(messages=[{"role": "user", "content": content}],
                                                  model=self.vl_model, task="continuity")
            if isinstance(vl, dict):
                outfit = vl.get("outfit_score")
                background = vl.get("background_score")
        score = combine_scores(face, outfit, background)
        return {"continuity_score": score, "overall_pass": score >= PASS_THRESHOLD,
                "face_score": face, "outfit_score": outfit, "background_score": background}
