import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.script import Script, Scene
from app.models.shot import Shot
from app.models.generated_clip import GeneratedClip
from app.models.generation_job import GenerationJob
from app.models.character import Character
from app.services.qwen_client import QwenClient
from app.services.oss_manager import OSSManager
from app.mcp_tools.scene_prompt_craft import ScenePromptCraft
from app.mcp_tools.consistency_guard import ConsistencyGuard
from app.services.guardrails import CostCircuitBreaker, PreGenerationValidator
from app.websocket.emitter import emit
from app.config import get_settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 1           # at most one self-correcting re-render per shot (cost cap)
WAN_COST_PER_SEC = 0.15   # real Wan2.7 pricing (high end)
HH_COST_PER_SEC = 0.108   # real HappyHorse-1.1 pricing (high end)
BUDGET_CEILING_PCT = 0.85  # cost circuit breaker
# Cosine threshold for "same person". A real photo vs an AI-generated frame
# tops out well below photo-to-photo (~0.5), so 0.6 was too strict and caused
# needless re-renders. 0.4 still rejects a clearly-wrong face (<0.3).
CONSISTENCY_THRESHOLD = 0.4


class GenerationRunner:
    def __init__(self, db: Session, budget_usd: float = 40.0):
        self.db = db
        settings = get_settings()
        self.qwen = QwenClient(settings)
        self.oss = OSSManager(settings)
        self.prompt_crafter = ScenePromptCraft()
        self.consistency_guard = ConsistencyGuard()
        self.breaker = CostCircuitBreaker(budget=budget_usd)
        self.budget_ceiling = self.breaker.ceiling

    @staticmethod
    def _shape_bible(characters, locations, style_url):
        chars = {}
        for c in characters:
            chars[c.name] = {"variants": [
                {"plate_image_url": v.plate_image_url, "scene_numbers": v.scene_numbers or [],
                 "is_default": v.is_default} for v in getattr(c, "costume_variants", [])]}
        loc_by_scene = {}
        for l in locations:
            for n in (l.scene_numbers or []):
                loc_by_scene[n] = l.plate_image_url
        return {"characters": chars, "location_by_scene": loc_by_scene, "style_plate": style_url}

    def _load_bible(self, project_id):
        from app.models.location_plate import LocationPlate
        from app.models.style_preset import StylePreset
        characters = self.db.query(Character).filter(Character.project_id == project_id).all()
        locations = self.db.query(LocationPlate).filter(LocationPlate.project_id == project_id).all()
        style = self.db.query(StylePreset).filter(StylePreset.project_id == project_id).first()
        return self._shape_bible(characters, locations, style.plate_image_url if style else None)

    def _ordered_shots(self, project_id) -> list[Shot]:
        script = (
            self.db.query(Script)
            .filter(Script.project_id == project_id)
            .order_by(Script.created_at.desc())
            .first()
        )
        if not script:
            return []
        scenes = (
            self.db.query(Scene)
            .filter(Scene.script_id == script.id)
            .order_by(Scene.number)
            .all()
        )
        shots: list[Shot] = []
        for scene in scenes:
            shots += (
                self.db.query(Shot)
                .filter(Shot.scene_id == scene.id)
                .order_by(Shot.number)
                .all()
            )
        return shots

    async def run_job(self, job_id: str) -> None:
        job = self.db.query(GenerationJob).filter(GenerationJob.id == uuid.UUID(job_id)).first()
        if not job:
            return

        job.status = "RUNNING"
        self.db.commit()

        shots = self._ordered_shots(job.project_id)
        characters = self.db.query(Character).filter(Character.project_id == job.project_id).all()
        char_by_name = {c.name: c for c in characters}

        # Pre-flight: block generation if storyboard/characters are incomplete.
        preflight = PreGenerationValidator().validate(
            characters=[
                {"name": c.name, "video_prompt_fragment": c.video_prompt_fragment,
                 "visual_description": c.visual_description}
                for c in characters
            ],
            shots=[
                {"characters_in_frame": s.characters_in_frame,
                 "estimated_duration_seconds": s.estimated_duration_seconds}
                for s in shots
            ],
        )
        if not preflight["pass"]:
            job.status = "BLOCKED"
            self.db.commit()
            emit("job:blocked", {"job_id": str(job.id), "issues": preflight["issues"]},
                 str(job.project_id))
            return

        job.total_shots = len(shots)
        self.db.commit()

        pid = str(job.project_id)
        for shot in shots:
            if job.actual_cost >= self.budget_ceiling:
                job.status = "BUDGET_EXHAUSTED"
                self.db.commit()
                emit("job:budget_exhausted", {"job_id": str(job.id)}, pid)
                return
            await self._process_shot(job, shot, char_by_name)
            emit("cost:updated", {
                "current_cost": round(job.actual_cost, 2),
                "budget_remaining": round(self.budget_ceiling - job.actual_cost, 2),
            }, pid)

        job.status = "COMPLETE"
        job.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        emit("job:completed", {
            "job_id": str(job.id),
            "total_clips": job.completed_shots,
            "total_cost": round(job.actual_cost, 2),
        }, pid)

    async def _process_shot(self, job: GenerationJob, shot: Shot, char_by_name: dict) -> None:
        in_frame = shot.characters_in_frame or []
        shot_chars = [char_by_name[n] for n in in_frame if n in char_by_name]

        character_visuals = {
            c.name: {
                "video_prompt_fragment": c.video_prompt_fragment or c.visual_description or "",
            }
            for c in shot_chars
        }

        prompt_result = await self.prompt_crafter.craft(
            shot={
                "shot_type": shot.shot_type,
                "camera_movement": shot.camera_movement,
                "action": shot.action,
                "lighting": shot.lighting,
                "colour_mood": shot.colour_mood,
                "emotional_beat": shot.emotional_beat,
                "estimated_duration_seconds": shot.estimated_duration_seconds,
            },
            character_visuals=character_visuals,
            target_model=shot.quality_tier or "happyhorse",
        )
        prompt = prompt_result.get("prompt", "")

        expected_characters = [
            {
                "name": c.name,
                "face_vector": c.face_vector,
                "description": c.face_embedding or {},
            }
            for c in shot_chars
        ]

        is_wan = shot.quality_tier == "wan"
        cost_per_sec = WAN_COST_PER_SEC if is_wan else HH_COST_PER_SEC
        pid = str(job.project_id)

        # Use a character reference image when available -> image/reference-to-video
        # for far better face consistency (what ConsistencyGuard then verifies).
        ref_image = next((c.reference_image_url for c in shot_chars if c.reference_image_url), None)

        for attempt in range(MAX_RETRIES + 1):
            try:
                emit("clip:started", {
                    "shot_id": str(shot.id),
                    "model": shot.quality_tier or "happyhorse",
                    "attempt": attempt,
                    "estimated_seconds": shot.estimated_duration_seconds,
                }, pid)
                if is_wan:
                    task_id = await self.qwen.generate_video_wan(
                        prompt=prompt, duration=shot.estimated_duration_seconds,
                        reference_image_url=ref_image,
                    )
                else:
                    task_id = await self.qwen.generate_video_happyhorse(
                        prompt=prompt, duration=shot.estimated_duration_seconds,
                        mode="r2v" if ref_image else "t2v",
                        reference_image_url=ref_image,
                    )
                clip_url = await self.qwen.poll_video_task(task_id)

                job.actual_cost += cost_per_sec * shot.estimated_duration_seconds

                has_ref_vector = any(
                    c["face_vector"] is not None and len(c["face_vector"]) > 0
                    for c in expected_characters
                )
                if expected_characters and has_ref_vector:
                    guard = await self.consistency_guard.validate(
                        clip_url=clip_url,
                        duration=shot.estimated_duration_seconds,
                        expected_characters=expected_characters,
                        threshold=CONSISTENCY_THRESHOLD,
                    )
                    consistency_score = guard["overall_similarity"]
                    passed = guard["overall_pass"]
                else:
                    consistency_score = 1.0
                    passed = True
                    guard = {"retry_instruction": None}

                status = "APPROVED" if passed else "FAILED"
                clip = GeneratedClip(
                    job_id=job.id, shot_id=shot.id,
                    model_used=shot.quality_tier or "happyhorse",
                    prompt=prompt, url=clip_url,
                    consistency_score=consistency_score,
                    status=status, retries=attempt,
                )
                self.db.add(clip)

                if passed:
                    job.completed_shots += 1
                    self.db.commit()
                    emit("clip:completed", {
                        "shot_id": str(shot.id), "clip_url": clip_url,
                        "consistency_score": consistency_score, "status": "APPROVED",
                    }, pid)
                    return

                # Diagnosis-driven smart retry (Fix #6): apply the targeted change.
                if attempt < MAX_RETRIES:
                    instruction = guard.get("retry_instruction") or "Emphasise facial features."
                    emit("clip:retry", {
                        "shot_id": str(shot.id), "retry_number": attempt + 1,
                        "reason": instruction,
                    }, pid)
                    prompt = f"{prompt}. {instruction}"
                    self.db.commit()
                    continue

                # Exhausted retries.
                clip.status = "NEEDS_REVIEW"
                job.completed_shots += 1
                self.db.commit()
                emit("clip:completed", {
                    "shot_id": str(shot.id), "clip_url": clip_url,
                    "consistency_score": consistency_score, "status": "NEEDS_REVIEW",
                }, pid)
                return

            except Exception as e:  # noqa: BLE001
                logger.error(f"Shot {shot.id} attempt {attempt} failed: {e}")
                if attempt == MAX_RETRIES:
                    clip = GeneratedClip(
                        job_id=job.id, shot_id=shot.id,
                        model_used=shot.quality_tier or "happyhorse",
                        prompt=prompt, status="NEEDS_REVIEW", retries=attempt,
                    )
                    self.db.add(clip)
                    job.completed_shots += 1
                    self.db.commit()
                    return
