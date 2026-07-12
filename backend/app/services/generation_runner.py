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
from app.services.reference_stack import WIDE_FRAMINGS, build_reference_stack_labeled
from app.services.set_dresser import setting_for_shot
from app.services.clip_store import persist_clip_url
from app.services.frame_sampler import extract_last_frame
from app.services.cost_ledger import record_video
from app.websocket.emitter import emit
from app.websocket.tool_events import tool_event, tool_run
from app.agents.reporter import report_agent
from app.config import get_settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 1           # at most one self-correcting re-render per shot (cost cap)
WAN_COST_PER_SEC = 0.15   # real Wan2.7 pricing (high end)
HH_COST_PER_SEC = 0.108   # real HappyHorse-1.1 pricing (high end)
BUDGET_CEILING_PCT = 0.85  # cost circuit breaker
VIDEO_RATIO = "9:16"       # default delivery format (per-drama override on Project)


def stable_seed(project_id: str, shot_id) -> int:
    """Deterministic per-shot seed: the same shot always renders with the
    same seed, so a re-render differs only by what changed on purpose
    (prompt, references) — not by RNG luck."""
    import hashlib
    digest = hashlib.sha1(f"{project_id}:{shot_id}".encode()).hexdigest()
    return int(digest[:8], 16) % 2_147_483_647


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
                 "is_default": v.is_default,
                 # the wardrobe TEXT rides along: the prompt must dress the
                 # character in this scene's outfit, or a swapped costume only
                 # exists in the reference image and the render ignores it
                 "outfit_description": getattr(v, "outfit_description", None),
                 # the continuity agent's face-lock check reads THIS — without
                 # it every clip scores face=None and the check is dead.
                 # list() so a pgvector numpy array survives `if not ref`.
                 "face_vector": (list(v.face_vector)
                                 if v.face_vector is not None else None)}
                for v in getattr(c, "costume_variants", [])]}
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
        # picked up: keep the pipeline lit through the pre-render phases
        # (voice synth, duration fit, preflight) before the first shot event
        emit("stage:progress", {"stage": "generate", "status": "update",
             "agent": "Renderer", "label": "Preparing the studio"},
             str(job.project_id))

        # Spend ceiling comes from THIS drama's budget, not a global default.
        from app.models.project import Project
        project = self.db.query(Project).filter(Project.id == job.project_id).first()
        if project and project.credit_budget:
            self.breaker = CostCircuitBreaker(budget=float(project.credit_budget))
            self.budget_ceiling = self.breaker.ceiling
        # Delivery format the user picked at creation (vertical by default).
        self._video_ratio = (getattr(project, "video_ratio", None) or VIDEO_RATIO)

        # ── Audio-first: synthesize the dialogue BEFORE rendering and fit each
        # speaking shot's duration to its real line audio, so a two-person
        # exchange gets pictures long enough to hold both voices. The lines are
        # reused at export (not paid for twice). Never fatal to the render.
        try:
            from app.models.line_audio import LineAudio
            if not self.db.query(LineAudio).filter(
                    LineAudio.project_id == job.project_id).count():
                from app.agent.pipeline_ops import synth_dialogue_op
                with tool_run(job.project_id, "generate", "synth_voices",
                              "Audio Mixer") as t:
                    n_lines = await synth_dialogue_op(self.db, str(job.project_id))
                    t["artifact"] = f"{n_lines} lines"
            from app.services.shot_duration_fitter import fit_project_shot_durations
            with tool_run(job.project_id, "generate", "fit_durations", "Director") as t:
                fitted = fit_project_shot_durations(self.db, str(job.project_id))
                t["artifact"] = f"{fitted} shots resized"
            if fitted:
                logger.info(f"Audio-first fit: {fitted} shot duration(s) adjusted")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Audio-first duration fit skipped: {e}")

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

        # Resume, never re-pay: a shot with an APPROVED take (from any job of
        # this drama) is not re-rendered — re-running generation only fills
        # failures and gaps instead of re-billing the whole plan.
        from app.models.generated_clip import GeneratedClip as _Clip
        prior_job_ids = [j.id for j in
                         self.db.query(GenerationJob)
                         .filter(GenerationJob.project_id == job.project_id).all()]
        self._approved_shot_ids = {
            sid for sid, in self.db.query(_Clip.shot_id)
            .filter(_Clip.job_id.in_(prior_job_ids),
                    _Clip.status == "APPROVED",
                    _Clip.url.isnot(None)).all()} if prior_job_ids else set()

        # Deferred shots were cut by the allocator to fit the spend cap.
        job.total_shots = len([s for s in shots
                               if (s.quality_tier or "") != "deferred"
                               and s.id not in self._approved_shot_ids])
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

        # Prompt-craft and continuity LLM calls inside the scene tasks inherit
        # this context, so their tokens land on this drama's ledger too.
        from app.services.usage_tracker import track_project
        with track_project(pid, self.db):
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
            tool_event(pid, "generate", "dispatch_video", "failed", agent="Renderer",
                       error="stopped at the spend cap")
            emit("job:budget_exhausted", {"job_id": str(job.id)}, pid)
            return
        job.status = "COMPLETE"
        job.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        tool_event(pid, "generate", "dispatch_video", "succeeded", agent="Renderer",
                   artifact=f"{job.completed_shots} clips")
        emit("job:completed", {
            "job_id": str(job.id),
            "total_clips": job.completed_shots,
            "total_cost": round(job.actual_cost, 2),
        }, pid)
        # Full-auto: the finished episode renders itself — dialogue placed,
        # captions burned, vertical canvas — with no click in between.
        if getattr(job, "auto_export", False):
            try:
                from app.workers.export_worker import run_export
                run_export.delay(pid, str(job.id))
                emit("export.autostarted", {"job_id": str(job.id)}, pid)
                emit("stage:progress", {"stage": "export", "status": "started",
                     "agent": "Editor", "label": "Queueing the final cut"}, pid)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"auto-export dispatch failed: {e}")

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
            r2._video_ratio = getattr(self, "_video_ratio", VIDEO_RATIO)

            job2 = db2.query(GenerationJob).filter(GenerationJob.id == self._job_id).first()
            if job2 is None:
                return
            pid = str(job2.project_id)
            char_by_name = {c.name: c for c in
                            db2.query(Character).filter(Character.project_id == job2.project_id).all()}
            shots = db2.query(Shot).filter(Shot.scene_id == scene.id).order_by(Shot.number).all()

            scene_anchor = None
            set_json = getattr(scene, "set_json", None)
            # Continuity de-dup runs over the shots that actually render (the
            # allocator may have cut some), so each prompt sees the real
            # previous/next picture — never a deferred shot. Prev/next stay
            # within the scene: a scene change is a clean cut, so the first
            # shot has no "previous" to continue from.
            already_good = getattr(self, "_approved_shot_ids", set())
            ordered = [s for s in shots if (s.quality_tier or "") != "deferred"]

            # lip-sync inputs: the scene's synthesized lines (audio-first, so
            # they exist before rendering) + which shots speak, in order. The
            # k-th speaking shot speaks the k-th line — same convention as
            # place_dialogue, so mouth and overlay can't disagree.
            from app.services.lipsync import pick_lipsync_line
            from app.models.line_audio import LineAudio
            # over ALL non-deferred shots of the scene, NOT `active`: on a
            # resume run `active` excludes already-approved shots, which would
            # shift every speaking index and drive mouths with the WRONG line
            speaking_ids = [s.id for s in shots
                            if (s.quality_tier or "") != "deferred"
                            and (s.dialogue or "").strip()]
            line_rows = (db2.query(LineAudio)
                         .filter(LineAudio.project_id == job2.project_id,
                                 LineAudio.scene_number == scene.number)
                         .order_by(LineAudio.line_index).all())
            scene_lines = [{"audio_url": r.audio_url,
                            "character_name": r.character_name,
                            "duration": r.duration_seconds}
                           for r in line_rows if r.audio_url]
            for i, shot in enumerate(ordered):
                if self._cancelled:
                    break
                if shot.id in already_good:
                    # resume: this shot keeps its approved clip, but its stored
                    # poster IS its last frame — seed the chain with it so the
                    # NEXT shot can still anchor a wan continuation (and lip-sync)
                    # to the real previous picture instead of getting nothing
                    seed = (db2.query(GeneratedClip.poster_url)
                            .filter(GeneratedClip.shot_id == shot.id,
                                    GeneratedClip.poster_url.isnot(None))
                            .order_by(GeneratedClip.created_at.desc())
                            .first())
                    if seed and seed[0]:
                        prev_last_frame = seed[0]
                        if (scene_anchor is None
                                and str(shot.shot_type or "").upper() in WIDE_FRAMINGS):
                            scene_anchor = prev_last_frame
                    continue
                prev_action = ordered[i - 1].action if i > 0 else None
                next_action = ordered[i + 1].action if i < len(ordered) - 1 else None
                scene_setting, state_changed = setting_for_shot(
                    set_json, scene.location, shot.number)
                # world-graph pass: does an active EVENT override this
                # location's default environmental behavior? (concert crowd
                # stops cheering in the shot where the performer collapses)
                from app.graph.environment_graph import resolve_environment
                environment = resolve_environment(
                    f"{scene.heading or ''} {scene.location or ''}",
                    f"{shot.action or ''}. {shot.emotional_beat or ''}")
                prev_last_frame = await r2._process_shot(
                    job2, shot, char_by_name, bible, scene.number, prev_last_frame,
                    scene_anchor_url=scene_anchor, scene_setting=scene_setting,
                    suppress_location=state_changed,
                    prev_action=prev_action, next_action=next_action,
                    lipsync_line=pick_lipsync_line(shot.id, speaking_ids, scene_lines),
                    environment=environment)
                # the first wide shot's closing frame anchors the room for the
                # rest of the scene — a run of close-ups can't erase the set
                if (scene_anchor is None and prev_last_frame
                        and str(shot.shot_type or "").upper() in WIDE_FRAMINGS):
                    scene_anchor = prev_last_frame
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

    async def _craft_prompt(self, shot, char_by_name, scene_setting=None,
                            prev_action=None, next_action=None, foreground=None,
                            environment=None,
                            outfits=None, blocking=None, lipsync=False) -> str:
        in_frame = shot.characters_in_frame or []
        fg = set(foreground or [])
        shot_chars = [char_by_name[n] for n in in_frame if n in char_by_name]
        character_visuals = {
            c.name: {"video_prompt_fragment": c.video_prompt_fragment or c.visual_description or "",
                     **({"outfit_this_shot": outfits[c.name]}
                        if outfits and c.name in outfits else {})}
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
            scene_setting=scene_setting,
            prev_action=prev_action,
            next_action=next_action,
            foreground_characters=[n for n in in_frame if n in fg],
            blocking=blocking,
            lipsync=lipsync,
            environment=environment,
        )
        return result

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

    async def _process_shot(self, job, shot, char_by_name, bible, scene_number,
                            prev_last_frame_url, scene_anchor_url=None,
                            scene_setting=None, suppress_location=False,
                            prev_action=None, next_action=None,
                            lipsync_line=None, environment=None):
        pid = str(job.project_id)
        in_frame = shot.characters_in_frame or []
        foreground = [n for n in (getattr(shot, "foreground_characters", None) or [])
                      if n in in_frame]
        is_wan = shot.quality_tier == "wan"
        model_cap = 5 if is_wan else 9
        # this scene's wardrobe, per character — fed into the PROMPT, not just
        # the reference stack, so an updated costume actually renders
        from app.services.wardrobe_planner import map_variant_for_scene
        outfits = {}
        for n in in_frame:
            ch_b = bible["characters"].get(n)
            if ch_b:
                v = map_variant_for_scene(ch_b.get("variants", []), scene_number)
                if v and (v.get("outfit_description") or "").strip():
                    outfits[n] = v["outfit_description"].strip()
        ref_stack, ref_provenance = build_reference_stack_labeled(
            characters_in_frame=in_frame, scene_number=scene_number, bible=bible,
            prev_last_frame_url=prev_last_frame_url, model_cap=model_cap,
            shot_type=shot.shot_type, scene_anchor_url=scene_anchor_url,
            suppress_location=suppress_location, foreground_characters=foreground)
        seed = stable_seed(pid, shot.id)

        emit("generation.shot.started", {"scene_number": scene_number,
             "shot_number": shot.number, "index": job.completed_shots + 1,
             "total": job.total_shots}, pid)
        tool_event(pid, "generate", "dispatch_video", "started", agent="Renderer",
                   index=job.completed_shots + 1, total=job.total_shots)
        # Legacy event kept for backward compatibility with the live-generation UI,
        # which still listens for clip:* events.
        emit("clip:started", {"shot_id": str(shot.id),
             "model": shot.quality_tier or "happyhorse"}, pid)

        for attempt in range(MAX_RETRIES + 1):
            try:
                ratio = getattr(self, "_video_ratio", VIDEO_RATIO)
                # the lip decision comes BEFORE prompt crafting: a mouth-driven
                # shot is framed openly talking, every other spoken line gets
                # mouth-hiding coverage — the crafter needs to know which
                from app.services.lipsync import lipsync_media, speaker_matches
                frame_anchor = (prev_last_frame_url or scene_anchor_url) if is_wan else None
                lip = None
                if is_wan:
                    lip = (lipsync_line
                           # a poll-time lip failure must degrade on the
                           # retry, not repeat itself
                           if (attempt == 0
                               and get_settings().lipsync_enabled
                               and frame_anchor
                               and lipsync_line
                               and lipsync_line.get("audio_url")
                               # an over-long driving track risks a wan-side
                               # rejection; unknown duration is treated as unsafe
                               and (lipsync_line.get("duration") or 0) > 0
                               and lipsync_line["duration"] <= shot.estimated_duration_seconds
                               and speaker_matches(lipsync_line, in_frame, foreground))
                           else None)
                tool_event(pid, "generate", "prompt_craft", "started", agent="Director",
                           index=job.completed_shots + 1, total=job.total_shots)
                crafted = await self._craft_prompt(
                    shot, char_by_name, scene_setting, prev_action, next_action,
                    foreground=foreground, outfits=outfits,
                    blocking=getattr(shot, "blocking_json", None),
                    lipsync=bool(lip), environment=environment)
                prompt = crafted.get("prompt", "")
                # the crafter has ALWAYS produced a negative prompt; until now
                # it was dropped on the floor before dispatch
                negative = (crafted.get("negative_prompt") or "").strip() or None
                # persist the transformation so the UI can show beat -> prompt
                # -> negative -> resolved environment (and why it won)
                shot.prompt_json = {"action": shot.action, "prompt": prompt,
                                    "negative_prompt": negative,
                                    "environment": environment,
                                    "repairs": crafted.get("repairs")}
                tool_event(pid, "generate", "prompt_craft", "succeeded", agent="Director")
                used_tier = shot.quality_tier or "happyhorse"
                if is_wan:
                    # wan2.7-i2v does NOT take identity references — its media
                    # schema is first_frame / last_frame / driving_audio /
                    # first_clip only. Give wan its REAL jobs: continue the
                    # scene from the previous shot's last frame, and when this
                    # shot speaks exactly one line with one visible speaker,
                    # DRIVE the mouth with that line's own TTS audio. Any
                    # failure falls down the chain: lip-sync -> plain
                    # first-frame -> happyhorse r2v. Never blocks the shot.
                    task_id = None
                    if lip:
                        try:
                            task_id = await self.qwen.generate_video_wan(
                                prompt=prompt, duration=shot.estimated_duration_seconds,
                                reference_media=lipsync_media(frame_anchor, lip["audio_url"]),
                                seed=seed, ratio=ratio, negative_prompt=negative)
                            logger.info("shot %s: lip-synced to its line", shot.id)
                        except Exception as le:  # noqa: BLE001 — never blocks
                            logger.warning("lip-sync dispatch failed for shot %s (%s) — "
                                           "falling back to plain first-frame", shot.id, le)
                    if task_id is None and frame_anchor:
                        try:
                            task_id = await self.qwen.generate_video_wan(
                                prompt=prompt, duration=shot.estimated_duration_seconds,
                                reference_media=[{"type": "first_frame", "url": frame_anchor}],
                                seed=seed, ratio=ratio, negative_prompt=negative)
                        except Exception as we:  # noqa: BLE001 — chain to happyhorse
                            logger.warning("wan first-frame failed for shot %s (%s) — "
                                           "falling back to happyhorse r2v", shot.id, we)
                    if task_id is None:
                        if not frame_anchor:
                            logger.info("shot %s: wan has no frame to continue from — "
                                        "rendering on happyhorse r2v with the bible stack",
                                        shot.id)
                        used_tier = "happyhorse"
                        task_id = await self.qwen.generate_video_happyhorse(
                            prompt=prompt, duration=shot.estimated_duration_seconds,
                            mode="r2v" if ref_stack else "t2v",
                            reference_media=ref_stack or None,
                            seed=seed, ratio=ratio, negative_prompt=negative)
                else:
                    task_id = await self.qwen.generate_video_happyhorse(
                        prompt=prompt, duration=shot.estimated_duration_seconds,
                        mode="r2v" if ref_stack else "t2v", reference_media=ref_stack or None,
                        seed=seed, ratio=ratio, negative_prompt=negative)
                clip_url = await self.qwen.poll_video_task(task_id)
                # DashScope URLs are signed and expire (~24h) — keep our own copy
                clip_url = await asyncio.to_thread(
                    persist_clip_url, pid, f"shot_{shot.id}", clip_url)

                emit("continuity.scoring.started", {"shot_id": str(shot.id)}, pid)
                tool_event(pid, "generate", "verify_face", "started", agent="Continuity",
                           index=job.completed_shots + 1, total=job.total_shots)
                guard = await self.continuity.validate(
                    clip_url=clip_url, duration=shot.estimated_duration_seconds,
                    characters_in_frame=in_frame, bible=bible, scene_number=scene_number,
                    foreground_characters=foreground)
                emit("continuity.scoring.completed", {"shot_id": str(shot.id), "scores": guard}, pid)
                tool_event(pid, "generate", "verify_face", "succeeded", agent="Continuity",
                           artifact=f"scored {guard['continuity_score']}%")
                report_agent(self.db, str(job.project_id), agent="continuity", stage="generation",
                             decision={"continuity_score": guard["continuity_score"],
                                       "face": guard.get("face_score"), "outfit": guard.get("outfit_score"),
                                       "background": guard.get("background_score")},
                             rationale=("passed" if guard["overall_pass"] else "flagged for review"),
                             confidence=guard["continuity_score"] / 100.0)

                status = "APPROVED" if guard["overall_pass"] else "NEEDS_REVIEW"
                # the clip's audio policy, decided ONCE (VAD + Qwen ASR) and
                # stored — the editor preview and the export worker both read
                # this verdict, so what you hear is what ships
                audio_policy = None
                try:
                    from app.services.audio_policy import bed_decision, speech_onset
                    has_dlg = bool((shot.dialogue or "").strip())
                    a_mute, a_vol = bed_decision(clip_url, has_dlg)
                    from app.services.video_stitcher import VideoStitcher
                    real_dur = VideoStitcher._duration(clip_url)
                    audio_policy = {"mute": a_mute, "volume": a_vol,
                                    "onset": (speech_onset(clip_url)
                                              if has_dlg else None),
                                    # the clip's REAL length: models render a
                                    # "10s" request ~7.6s, and every consumer
                                    # (timeline, captions, export) must agree
                                    "duration": real_dur if real_dur > 0 else None}
                except Exception as ae:  # noqa: BLE001 — policy is best-effort
                    logger.warning(f"audio policy skipped for shot {shot.id}: {ae}")
                tool_event(pid, "generate", "write_clip_db", "started", agent="Renderer")
                clip = GeneratedClip(
                    job_id=job.id, shot_id=shot.id,
                    # the tier that ACTUALLY rendered (a wan shot with no frame
                    # anchor falls back to happyhorse) — costs stay truthful
                    model_used=used_tier, prompt=prompt, url=clip_url,
                    consistency_score=guard["continuity_score"],
                    face_score=guard.get("face_score"), outfit_score=guard.get("outfit_score"),
                    background_score=guard.get("background_score"),
                    references_json=ref_provenance, seed=seed,
                    status=status, retries=attempt, audio_json=audio_policy)
                self.db.add(clip)
                job.completed_shots += 1
                self.db.commit()
                tool_event(pid, "generate", "write_clip_db", "succeeded", agent="Renderer",
                           artifact=f"{job.completed_shots} clip rows")
                if attempt > 0:
                    tool_event(pid, "generate", "self_correct", "succeeded",
                               agent="Renderer", artifact="recovered on retry")
                amt = record_video(self.db, str(job.project_id), shot.estimated_duration_seconds,
                                   used_tier, ref_id=str(clip.id))
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
                frame_url = self._store_last_frame(pid, shot, clip_url)
                if frame_url:
                    # the chained frame doubles as the clip's poster still — it
                    # outlives the clip URL's expiry (dashboards, analytics
                    # evidence), and the first one names the drama's card
                    try:
                        clip.poster_url = frame_url
                        from app.models.project import Project
                        project = (self.db.query(Project)
                                   .filter(Project.id == job.project_id).first())
                        if project and not project.poster_url:
                            project.poster_url = frame_url
                        self.db.commit()
                    except Exception as e:  # noqa: BLE001
                        logger.warning(f"poster persist skipped: {e}")
                return frame_url
            except Exception as e:  # HARD failure only -> at most one retry
                logger.error(f"Shot {shot.id} attempt {attempt} hard-failed: {e}")
                if attempt < MAX_RETRIES:
                    # the self-correct pass: same shot, fresh attempt
                    tool_event(pid, "generate", "self_correct", "started", agent="Renderer",
                               index=attempt + 1, total=MAX_RETRIES, error=str(e))
                else:
                    tool_event(pid, "generate", "self_correct", "failed", agent="Renderer",
                               error=str(e))
                if attempt >= MAX_RETRIES:
                    self.db.add(GeneratedClip(
                        job_id=job.id, shot_id=shot.id,
                        model_used=shot.quality_tier or "happyhorse", prompt="",
                        references_json=ref_provenance, seed=seed,
                        status="NEEDS_REVIEW", retries=attempt))
                    job.completed_shots += 1
                    self.db.commit()
                    return None
        return None
