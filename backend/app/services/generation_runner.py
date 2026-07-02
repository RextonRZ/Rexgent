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
from app.services.guardrails import CostCircuitBreaker, PreGenerationValidator
from app.services.reference_stack import build_reference_stack
from app.services.frame_sampler import extract_last_frame
from app.services.cost_ledger import record_video
from app.websocket.emitter import emit
from app.agents.reporter import report_agent
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
        from app.mcp_tools.continuity_agent import ContinuityAgent
        self.continuity = ContinuityAgent()
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
        bible = self._load_bible(job.project_id)
        script = (self.db.query(Script).filter(Script.project_id == job.project_id)
                  .order_by(Script.created_at.desc()).first())
        scenes = (self.db.query(Scene).filter(Scene.script_id == script.id)
                  .order_by(Scene.number).all()) if script else []
        for scene in scenes:
            prev_last_frame = None
            scene_shots = (self.db.query(Shot).filter(Shot.scene_id == scene.id)
                           .order_by(Shot.number).all())
            for shot in scene_shots:
                if job.actual_cost >= self.budget_ceiling:
                    job.status = "BUDGET_EXHAUSTED"
                    self.db.commit()
                    emit("job:budget_exhausted", {"job_id": str(job.id)}, pid)
                    return
                prev_last_frame = await self._process_shot(
                    job, shot, char_by_name, bible, scene.number, prev_last_frame)
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

    async def _craft_prompt(self, shot, char_by_name) -> str:
        in_frame = shot.characters_in_frame or []
        shot_chars = [char_by_name[n] for n in in_frame if n in char_by_name]
        character_visuals = {
            c.name: {"video_prompt_fragment": c.video_prompt_fragment or c.visual_description or ""}
            for c in shot_chars
        }
        result = await self.prompt_crafter.craft(
            shot={"shot_type": shot.shot_type, "camera_movement": shot.camera_movement,
                  "action": shot.action, "lighting": shot.lighting,
                  "colour_mood": shot.colour_mood, "emotional_beat": shot.emotional_beat,
                  "estimated_duration_seconds": shot.estimated_duration_seconds},
            character_visuals=character_visuals,
            target_model=shot.quality_tier or "happyhorse",
        )
        return result.get("prompt", "")

    def _store_last_frame(self, pid, shot, clip_url):
        try:
            frame_bytes = extract_last_frame(clip_url)
            if not frame_bytes:
                return None
            key = self.oss.get_project_path(pid, "chain", f"shot_{shot.id}_last.jpg")
            return self.oss.upload_bytes(frame_bytes, key, content_type="image/jpeg")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"last-frame extract failed for shot {shot.id}: {e}")
            return None

    async def _process_shot(self, job, shot, char_by_name, bible, scene_number, prev_last_frame_url):
        pid = str(job.project_id)
        in_frame = shot.characters_in_frame or []
        is_wan = shot.quality_tier == "wan"
        model_cap = 5 if is_wan else 9
        ref_stack = build_reference_stack(
            characters_in_frame=in_frame, scene_number=scene_number, bible=bible,
            prev_last_frame_url=prev_last_frame_url, model_cap=model_cap)

        emit("generation.shot.started", {"scene_number": scene_number,
             "shot_number": shot.number, "index": job.completed_shots + 1,
             "total": job.total_shots}, pid)

        for attempt in range(MAX_RETRIES + 1):
            try:
                prompt = await self._craft_prompt(shot, char_by_name)
                if is_wan:
                    task_id = await self.qwen.generate_video_wan(
                        prompt=prompt, duration=shot.estimated_duration_seconds,
                        reference_media=ref_stack or None)
                else:
                    task_id = await self.qwen.generate_video_happyhorse(
                        prompt=prompt, duration=shot.estimated_duration_seconds,
                        mode="r2v" if ref_stack else "t2v", reference_media=ref_stack or None)
                clip_url = await self.qwen.poll_video_task(task_id)

                emit("continuity.scoring.started", {"shot_id": str(shot.id)}, pid)
                guard = await self.continuity.validate(
                    clip_url=clip_url, duration=shot.estimated_duration_seconds,
                    characters_in_frame=in_frame, bible=bible, scene_number=scene_number)
                emit("continuity.scoring.completed", {"shot_id": str(shot.id), "scores": guard}, pid)
                report_agent(self.db, str(job.project_id), agent="continuity", stage="generation",
                             decision={"continuity_score": guard["continuity_score"],
                                       "face": guard.get("face_score"), "outfit": guard.get("outfit_score"),
                                       "background": guard.get("background_score")},
                             rationale=("passed" if guard["overall_pass"] else "flagged for review"),
                             confidence=guard["continuity_score"] / 100.0)

                status = "APPROVED" if guard["overall_pass"] else "NEEDS_REVIEW"
                clip = GeneratedClip(
                    job_id=job.id, shot_id=shot.id,
                    model_used=shot.quality_tier or "happyhorse", prompt=prompt, url=clip_url,
                    consistency_score=guard["continuity_score"],
                    face_score=guard.get("face_score"), outfit_score=guard.get("outfit_score"),
                    background_score=guard.get("background_score"),
                    status=status, retries=attempt)
                self.db.add(clip)
                job.completed_shots += 1
                self.db.commit()
                amt = record_video(self.db, str(job.project_id), shot.estimated_duration_seconds,
                                   shot.quality_tier or "happyhorse", ref_id=str(clip.id))
                job.actual_cost += amt
                if status == "NEEDS_REVIEW":
                    emit("continuity.flagged", {"shot_id": str(shot.id),
                         "continuity_score": guard["continuity_score"]}, pid)
                emit("generation.shot.completed", {"scene_number": scene_number,
                     "shot_number": shot.number, "clip_url": clip_url, "status": status}, pid)
                # SOFT failures do NOT loop — single generation on the happy path.
                return self._store_last_frame(pid, shot, clip_url)
            except Exception as e:  # HARD failure only -> at most one retry
                logger.error(f"Shot {shot.id} attempt {attempt} hard-failed: {e}")
                if attempt >= MAX_RETRIES:
                    self.db.add(GeneratedClip(
                        job_id=job.id, shot_id=shot.id,
                        model_used=shot.quality_tier or "happyhorse", prompt="",
                        status="NEEDS_REVIEW", retries=attempt))
                    job.completed_shots += 1
                    self.db.commit()
                    return None
        return None
