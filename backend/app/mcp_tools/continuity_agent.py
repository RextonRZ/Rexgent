import base64
from app.services.face_embedder import FaceEmbedder
from app.services.frame_sampler import sample_frames
from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.config import get_settings
from app.services.wardrobe_planner import map_variant_for_scene

FACE_W, OUTFIT_W, BG_W = 0.5, 0.25, 0.25
PASS_THRESHOLD = 55   # 0-100

# ArcFace cosine similarity lives on its own scale: genuine same-person pairs
# clear ~0.35 (buffalo_l's standard verification threshold) and clean matches
# sit near 0.5-0.7, while wrong faces cluster around 0-0.2. Shown raw as a
# percent, a STRONG 0.5 match reads as "50/100, failing".
GENUINE_SIM, STRONG_SIM = 0.35, 0.65


def calibrate_face_similarity(sim: float) -> float:
    """Map raw ArcFace cosine to 0-1 match confidence, the way production face
    APIs do: the genuine-pair threshold lands at 0.75 (a clear pass) and 0.65+
    saturates to 1.0; below-threshold similarities stay proportionally low."""
    if sim <= 0.0:
        return 0.0
    if sim >= STRONG_SIM:
        return 1.0
    if sim < GENUINE_SIM:
        return round(sim / GENUINE_SIM * 0.75, 4)
    return round(0.75 + (sim - GENUINE_SIM) / (STRONG_SIM - GENUINE_SIM) * 0.25, 4)


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

    async def validate(self, clip_url, duration, characters_in_frame, bible, scene_number,
                       foreground_characters=None) -> dict:
        frames = self._sample(clip_url, duration)
        fg = set(foreground_characters or [])
        # Only score faces we expect to SEE: a foreground occluder (back/shoulder
        # to camera) has no face in frame, so matching it would spuriously tank
        # the score on every reveal / over-the-shoulder shot.
        face_names = [n for n in characters_in_frame if n not in fg]
        # face: every detected face in every sampled frame, embedded once.
        # The old pass took only the LARGEST face per frame and averaged every
        # character against it — in a two-person shot each character was graded
        # against the other person's face half the time, capping a perfect
        # render near 50. Now each character is judged on their own best match
        # across all faces; identity drift still reads low because no detected
        # face matches the reference then.
        frame_faces = [fv for fr in frames for fv in self.embedder.model.embed_all(fr)]
        per_char = []
        for name in face_names:
            ch = bible["characters"].get(name)
            if not ch:
                continue
            v = map_variant_for_scene(ch.get("variants", []), scene_number)
            ref = (v or {}).get("face_vector")
            if not ref:
                continue
            sims = [self.embedder.compare_vectors(ref, fv) for fv in frame_faces]
            if sims:
                per_char.append(calibrate_face_similarity(max(sims)))
        face = round(sum(per_char) / len(per_char), 4) if per_char else None
        # outfit + background via one VL call on the middle frame
        outfit = background = None
        if frames:
            mid = frames[len(frames) // 2]
            b64 = base64.b64encode(mid).decode()
            # prefer a face-visible subject's plate for the outfit check
            outfit_names = face_names or characters_in_frame
            char_plate = next((map_variant_for_scene(bible["characters"][n].get("variants", []), scene_number)
                               for n in outfit_names if n in bible["characters"]), None)
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
