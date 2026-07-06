import asyncio
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
from app.services.clip_store import persist_clip_url
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
    _max_concurrency = 5

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

        # Spend ceiling comes from THIS drama's budget, not a global default.
        from app.models.project import Project
        project = self.db.query(Project).filter(Project.id == job.project_id).first()
        if project and project.credit_budget:
            self.breaker = CostCircuitBreaker(budget=float(project.credit_budget))
            self.budget_ceiling = self.breaker.ceiling

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

        # Scenes (ordered) for this job's latest script.
        script = (self.db.query(Script).filter(Script.project_id == job.project_id)
                  .order_by(Script.created_at.desc()).first())
        scenes = (self.db.query(Scene).filter(Scene.script_id == script.id)
                  .order_by(Scene.number).all()) if script else []

        import asyncio
        self._job_id = job.id
        self._spent = float(job.actual_cost or 0.0)
        self._cost_lock = asyncio.Lock()
        self._cancelled = False

        await self._run_scenes_concurrently(scenes, bible)

        # Reconcile counters from the DB (per-scene sessions wrote clips + cost events
        # independently, so recompute authoritative totals here to avoid lost updates).
        from app.models.generated_clip import GeneratedClip
        job.completed_shots = (self.db.query(GeneratedClip)
                               .filter(GeneratedClip.job_id == job.id).count())
        job.actual_cost = round(self._spent, 4)
        if self._cancelled:
            job.status = "BUDGET_EXHAUSTED"
            self.db.commit()
            emit("job:budget_exhausted", {"job_id": str(job.id)}, pid)
            return
        job.status = "COMPLETE"
        job.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        emit("job:completed", {
            "job_id": str(job.id),
            "total_clips": job.completed_shots,
            "total_cost": round(job.actual_cost, 2),
        }, pid)

    async def _run_scenes_concurrently(self, scenes, bible):
        # Scenes run in parallel for speed. Shots WITHIN a scene stay sequential and
        # chain frame-to-frame (see _run_scene). A scene change is a clean cut, so the
        # cross-scene look is held together by the shared location + style plates and
        # the per-scene lighting consistency the storyboard enforces — not a splice.
        import asyncio
        sem = asyncio.Semaphore(self._max_concurrency)

        async def guarded(scene):
            async with sem:
                await self._run_scene(scene, bible)

        await asyncio.gather(*(guarded(s) for s in scenes))

    async def _run_scene(self, scene, bible, incoming_last_frame=None):
        from app.database import get_session_factory
        from app.services.cost_rates import video_cost
        from app.models.generation_job import GenerationJob
        from app.models.shot import Shot
        import asyncio  # noqa: F401

        SessionLocal = get_session_factory()
        db2 = SessionLocal()
        prev_last_frame = incoming_last_frame
        try:
            # A scene-local runner sharing the stateless services but bound to db2,
            # so concurrent scenes never share a SQLAlchemy Session.
            r2 = GenerationRunner.__new__(GenerationRunner)
            r2.db = db2
            r2.qwen = self.qwen
            r2.oss = self.oss
            r2.continuity = self.continuity
            r2.prompt_crafter = self.prompt_crafter
            r2.budget_ceiling = self.budget_ceiling

            job2 = db2.query(GenerationJob).filter(GenerationJob.id == self._job_id).first()
            if job2 is None:
                return
            pid = str(job2.project_id)
            char_by_name = {c.name: c for c in
                            db2.query(Character).filter(Character.project_id == job2.project_id).all()}
            shots = db2.query(Shot).filter(Shot.scene_id == scene.id).order_by(Shot.number).all()

            for shot in shots:
                if self._cancelled:
                    break
                prev_last_frame = await r2._process_shot(
                    job2, shot, char_by_name, bible, scene.number, prev_last_frame)
                amt = video_cost(shot.estimated_duration_seconds, shot.quality_tier or "happyhorse")
                async with self._cost_lock:
                    self._spent += amt
                    if self._spent >= self.budget_ceiling:
                        self._cancelled = True
                    emit("cost:updated", {
                        "current_cost": round(self._spent, 2),
                        "budget_remaining": round(self.budget_ceiling - self._spent, 2),
                    }, pid)
        finally:
            db2.close()
        return prev_last_frame

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
                  "dialogue": shot.dialogue, "notes": getattr(shot, "notes", None),
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
            prev_last_frame_url=prev_last_frame_url, model_cap=model_cap,
            shot_type=shot.shot_type)

        emit("generation.shot.started", {"scene_number": scene_number,
             "shot_number": shot.number, "index": job.completed_shots + 1,
             "total": job.total_shots}, pid)
        # Legacy event kept for backward compatibility with the live-generation UI,
        # which still listens for clip:* events.
        emit("clip:started", {"shot_id": str(shot.id),
             "model": shot.quality_tier or "happyhorse"}, pid)

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
                # DashScope URLs are signed and expire (~24h) — keep our own copy
                clip_url = await asyncio.to_thread(
                    persist_clip_url, pid, f"shot_{shot.id}", clip_url)
                # TODO(dashboard): if the project has no poster_url yet, extract a
                # default poster here (frame_sampler.extract_frame_at(clip_url, 2.0)
                # -> OSS -> project.poster_url) so cards never ship empty.

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
                # Legacy event kept for backward compatibility with the live-generation UI,
                # which still listens for clip:* events.
                emit("clip:completed", {"shot_id": str(shot.id), "clip_url": clip_url,
                     "consistency_score": guard["continuity_score"], "status": status}, pid)
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
