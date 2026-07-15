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
from app.services.continuity_repair import repair_steps
from app.websocket.emitter import emit
from app.websocket.tool_events import tool_event
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


def _is_catastrophic(guard: dict, in_frame: list) -> bool:
    """A render that failed CATASTROPHICALLY — a black/empty frame, or a
    face-locked character the model dropped entirely — NOT a soft continuity
    miss. These are worth a fresh-seed re-roll regardless of the repair flag,
    so a black clip never ships when a re-render could save it."""
    if (guard.get("continuity_score") or 0) < 20:            # near-zero: garbage frame
        return True
    bg = guard.get("background_score")
    if bg is not None and bg < 0.15:                         # black / empty background
        return True
    if in_frame and guard.get("face_score") is None:         # a face was expected, none found
        return True
    return False


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
        # picked up: keep the pipeline lit through the pre-render phase
        # (preflight) before the first shot event
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

        # TTS synthesis removed: clips play their own NATIVE audio, so there is
        # no audio-first synth pass and no duration fit to line audio. Shots keep
        # the estimated_duration_seconds the storyboard already sized them with.
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
        if preflight.get("warnings"):
            # extras with no plate, and similar soft findings: surfaced, never
            # blocking — a missing extra identity must not stop generation
            logger.warning("preflight warnings for job %s: %s",
                           job.id, preflight["warnings"])
            emit("job:warnings", {"job_id": str(job.id),
                 "warnings": preflight["warnings"]}, str(job.project_id))
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
        from app.models.generation_job import GenerationJob
        from app.models.shot import Shot
        import asyncio  # noqa: F401

        SessionLocal = get_session_factory()
        db2 = SessionLocal()
        prev_last_frame = incoming_last_frame
        prev_clip = None
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

            # native-talk inputs: the scene's SCRIPT dialogue (character + line)
            # + which shots speak, in order. The k-th speaking shot speaks the
            # k-th line. The picked line names the on-camera speaker so
            # HappyHorse native-talk animates the right mouth.
            from app.services.lipsync import pick_lipsync_line
            # over ALL non-deferred shots of the scene, NOT `active`: on a
            # resume run `active` excludes already-approved shots, which would
            # shift every speaking index and drive mouths with the WRONG line
            speaking_ids = [s.id for s in shots
                            if (s.quality_tier or "") != "deferred"
                            and (s.dialogue or "").strip()]
            # Native-talk names the speaker from the SCRIPT's dialogue (character +
            # line): the model speaks the text itself, so no synthesized audio is
            # needed to know who talks.
            scene_lines = [{"character_name": ln.get("character"),
                            "text": ln.get("line")}
                           for ln in (scene.dialogue_json or [])
                           if (ln.get("line") or "").strip()]
            if not getattr(get_settings(), "multishot_enabled", False):
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
                            # a resumed shot has no fresh clip URL to continue
                            # from — do not let a stale clip carry over
                            prev_clip = None
                            if (scene_anchor is None
                                    and str(shot.shot_type or "").upper() in WIDE_FRAMINGS):
                                scene_anchor = prev_last_frame
                        continue
                    prev_action = ordered[i - 1].action if i > 0 else None
                    next_action = ordered[i + 1].action if i < len(ordered) - 1 else None
                    prev_in_frame = (ordered[i - 1].characters_in_frame or []) if i > 0 else []
                    scene_setting, state_changed = setting_for_shot(
                        set_json, scene.location, shot.number)
                    # world-graph pass: does an active EVENT override this
                    # location's default environmental behavior? (concert crowd
                    # stops cheering in the shot where the performer collapses)
                    from app.graph.environment_graph import resolve_environment
                    environment = resolve_environment(
                        f"{scene.heading or ''} {scene.location or ''}",
                        f"{shot.action or ''}. {shot.emotional_beat or ''}")
                    prev_last_frame, prev_clip, shot_spent = await r2._process_shot(
                        job2, shot, char_by_name, bible, scene.number, prev_last_frame,
                        scene_anchor_url=scene_anchor, scene_setting=scene_setting,
                        suppress_location=state_changed,
                        prev_action=prev_action, next_action=next_action,
                        lipsync_line=pick_lipsync_line(shot.id, speaking_ids, scene_lines, shot_dialogue=shot.dialogue),
                        environment=environment, prev_in_frame=prev_in_frame,
                        prev_shot_type=(ordered[i - 1].shot_type if i > 0 else None),
                        prev_clip_url=prev_clip)
                    # the first wide shot's closing frame anchors the room for the
                    # rest of the scene — a run of close-ups can't erase the set
                    if (scene_anchor is None and prev_last_frame
                            and str(shot.shot_type or "").upper() in WIDE_FRAMINGS):
                        scene_anchor = prev_last_frame
                    async with self._cost_lock:
                        self._spent += shot_spent
                        if self._spent >= self.budget_ceiling:
                            self._cancelled = True
                        emit("cost:updated", {
                            "current_cost": round(self._spent, 2),
                            "budget_remaining": round(self.budget_ceiling - self._spent, 2),
                        }, pid)
            else:
                # Multishot ON: group the scene's shots into beats — a run of
                # dialogue shots involving <=2 people renders as ONE wan
                # multi-shot clip instead of one render per shot. Everything
                # else (and any beat whose dispatch fails) stays a singleton,
                # rendered through the exact same _process_shot call as the
                # flag-off path above.
                async def _render_singleton(i, shot):
                    nonlocal prev_last_frame, prev_clip, scene_anchor
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
                            # a resumed shot has no fresh clip URL to continue
                            # from — do not let a stale clip carry over
                            prev_clip = None
                            if (scene_anchor is None
                                    and str(shot.shot_type or "").upper() in WIDE_FRAMINGS):
                                scene_anchor = prev_last_frame
                        return
                    prev_action = ordered[i - 1].action if i > 0 else None
                    next_action = ordered[i + 1].action if i < len(ordered) - 1 else None
                    prev_in_frame = (ordered[i - 1].characters_in_frame or []) if i > 0 else []
                    scene_setting, state_changed = setting_for_shot(
                        set_json, scene.location, shot.number)
                    from app.graph.environment_graph import resolve_environment
                    environment = resolve_environment(
                        f"{scene.heading or ''} {scene.location or ''}",
                        f"{shot.action or ''}. {shot.emotional_beat or ''}")
                    prev_last_frame, prev_clip, shot_spent = await r2._process_shot(
                        job2, shot, char_by_name, bible, scene.number, prev_last_frame,
                        scene_anchor_url=scene_anchor, scene_setting=scene_setting,
                        suppress_location=state_changed,
                        prev_action=prev_action, next_action=next_action,
                        lipsync_line=pick_lipsync_line(shot.id, speaking_ids, scene_lines, shot_dialogue=shot.dialogue),
                        environment=environment, prev_in_frame=prev_in_frame,
                        prev_shot_type=(ordered[i - 1].shot_type if i > 0 else None),
                        prev_clip_url=prev_clip)
                    if (scene_anchor is None and prev_last_frame
                            and str(shot.shot_type or "").upper() in WIDE_FRAMINGS):
                        scene_anchor = prev_last_frame
                    async with self._cost_lock:
                        self._spent += shot_spent
                        if self._spent >= self.budget_ceiling:
                            self._cancelled = True
                        emit("cost:updated", {
                            "current_cost": round(self._spent, 2),
                            "budget_remaining": round(self.budget_ceiling - self._spent, 2),
                        }, pid)

                from app.services.multishot import group_beats
                beats = group_beats(ordered, get_settings().multishot_max_shots,
                                    wan_primary=getattr(get_settings(), "wan_primary", False))
                idx = 0
                for unit in beats:
                    if self._cancelled:
                        break
                    if len(unit) == 1:
                        await _render_singleton(idx, unit[0])
                        idx += 1
                        continue
                    prev_shot_type_before = ordered[idx - 1].shot_type if idx > 0 else None
                    new_frame, new_clip, shot_spent = await r2._process_beat(
                        unit, job2, char_by_name, bible, scene.number, prev_last_frame,
                        scene_anchor_url=scene_anchor, prev_shot_type=prev_shot_type_before)
                    # book whatever the beat actually spent — full on success,
                    # 0.0 or partial on a post-dispatch failure — so a partial
                    # spend is never lost to the fallback
                    async with self._cost_lock:
                        self._spent += shot_spent
                        if self._spent >= self.budget_ceiling:
                            self._cancelled = True
                        emit("cost:updated", {
                            "current_cost": round(self._spent, 2),
                            "budget_remaining": round(self.budget_ceiling - self._spent, 2),
                        }, pid)
                    if new_clip is None:
                        # dispatch OR post-dispatch failed: fall back to per-shot
                        # rendering so the beat is never lost
                        for j, beat_shot in enumerate(unit):
                            if self._cancelled:
                                break
                            await _render_singleton(idx + j, beat_shot)
                    else:
                        prev_last_frame = new_frame
                        prev_clip = new_clip
                        last_shot = unit[-1]
                        if (scene_anchor is None
                                and str(last_shot.shot_type or "").upper() in WIDE_FRAMINGS):
                            scene_anchor = prev_last_frame
                    idx += len(unit)
        finally:
            db2.close()
        return prev_last_frame

    async def _craft_prompt(self, shot, char_by_name, scene_setting=None,
                            prev_action=None, next_action=None, foreground=None,
                            environment=None,
                            outfits=None, blocking=None, lipsync=False,
                            native_talk=False, speaker="", image_legend="",
                            to_wan=False) -> str:
        from app.services.guardrails import canonical_character, mask_offscreen_names
        in_frame = [canonical_character(n, char_by_name)
                    for n in (shot.characters_in_frame or [])]
        fg = set(foreground or [])
        shot_chars = [char_by_name[n] for n in in_frame if n in char_by_name]
        character_visuals = {
            c.name: {"video_prompt_fragment": c.video_prompt_fragment or c.visual_description or "",
                     **({"outfit_this_shot": outfits[c.name]}
                        if outfits and c.name in outfits else {})}
            for c in shot_chars
        }
        # An action naming a character NOT in this shot's frame ("glancing back at
        # Anna" in a Deok-hyun-only shot) makes the model hallucinate them — worst
        # on Wan. Strip off-frame cast names so only in-frame people can render.
        all_cast = list({c.name for c in char_by_name.values() if getattr(c, "name", None)})
        clean_action = mask_offscreen_names(shot.action, in_frame, all_cast)
        result = await self.prompt_crafter.craft(
            shot={"shot_type": shot.shot_type, "camera_movement": shot.camera_movement,
                  "action": clean_action, "lighting": shot.lighting,
                  "colour_mood": shot.colour_mood, "emotional_beat": shot.emotional_beat,
                  "dialogue": shot.dialogue, "notes": getattr(shot, "notes", None),
                  "director_json": getattr(shot, "director_json", None),
                  "estimated_duration_seconds": shot.estimated_duration_seconds},
            character_visuals=character_visuals,
            target_model=shot.quality_tier or "happyhorse",
            scene_setting=scene_setting,
            prev_action=prev_action,
            next_action=next_action,
            foreground_characters=[n for n in in_frame if n in fg],
            blocking=blocking,
            lipsync=lipsync,
            native_talk=native_talk,
            speaker=speaker,
            image_legend=image_legend,
            environment=environment,
            to_wan=to_wan,
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

    async def _dispatch_by_role(self, *, role, prompt, duration, seed, ratio,
                                negative, ref_stack, frame_anchor, prev_clip_url,
                                speaks=False, has_newcomers=False, has_faces=False):
        """Route a shot to a model by its identity role. Never-blocking: every
        path degrades to happyhorse r2v so a model surprise can't fail the shot.
        Returns (used_tier, task_id)."""
        from app.services.continuation_media import hold_media, r2v_media

        async def _happyhorse():
            return await self.qwen.generate_video_happyhorse(
                prompt=prompt, duration=duration,
                mode="r2v" if ref_stack else "t2v",
                reference_media=ref_stack or None,
                seed=seed, ratio=ratio, negative_prompt=negative)

        if getattr(get_settings(), "wan_primary", False):
            # Wan-primary: HappyHorse = talking shots, shots that must LOCK a
            # new/establishing face, AND reangles — an angle change must never
            # ride Wan continuation (it copies the previous frame and fights the
            # new framing; shot_roles doctrine). Wan = silent same-angle
            # continuation or scenery. Wan errors chain to happyhorse.
            if (speaks or has_newcomers or role == "continue_reangle"
                    or (role == "anchor" and has_faces)):
                return ("happyhorse", await _happyhorse())
            media = hold_media(first_clip_url=prev_clip_url, first_frame_url=frame_anchor)
            try:
                task = await self.qwen.generate_video_wan(
                    prompt=prompt, duration=duration, reference_media=media,
                    seed=seed, ratio=ratio, negative_prompt=negative)
                return ("wan", task)
            except Exception as e:  # noqa: BLE001 — chain to happyhorse, never block
                logger.warning("wan_primary wan dispatch failed (%s) — happyhorse", e)
                return ("happyhorse", await _happyhorse())

        if role in ("anchor", "entrance", "continue_reangle"):
            # Identity shots go to the reference model. happyhorse r2v is the SAFE
            # DEFAULT (reference-native, measured to hold faces better than wan r2v);
            # anchor_ref_model="wan" opts into wan2.7-r2v. Phase 3's harness picks
            # the winner from real scores. Either path degrades to happyhorse.
            if getattr(get_settings(), "anchor_ref_model", "happyhorse") == "wan":
                # wan r2v carries scene continuity via a TYPED first_frame on
                # entrance/reangle; anchor is establishing (no frame)
                ff = frame_anchor if role in ("entrance", "continue_reangle") else None
                media = r2v_media(ref_stack, first_frame_url=ff)
                if media:
                    try:
                        return ("wan_r2v", await self.qwen.generate_video_wan_r2v(
                            prompt=prompt, duration=duration, reference_media=media,
                            seed=seed, ratio=ratio, negative_prompt=negative))
                    except Exception as e:  # noqa: BLE001 — chain to happyhorse
                        logger.warning("wan r2v dispatch failed for role %s (%s) — "
                                       "falling back to happyhorse r2v", role, e)
            # happyhorse r2v: the previous frame already rides in the reference
            # stack as a reference_image, so no separate first_frame is needed
            return ("happyhorse", await _happyhorse())

        # continue_hold
        if getattr(get_settings(), "route_continuation_to_happyhorse", True):
            # Wan i2v continuation hard-fails when the previous clip is >= the
            # requested duration; HappyHorse r2v continues via the reference stack
            # (which already carries the prev frame) and does multi-person
            # native-talk. Flag OFF -> old wan i2v continuation path.
            return ("happyhorse", await _happyhorse())
        media = hold_media(first_clip_url=prev_clip_url, first_frame_url=frame_anchor)
        if media:
            try:
                task = await self.qwen.generate_video_wan(
                    prompt=prompt, duration=duration, reference_media=media,
                    seed=seed, ratio=ratio, negative_prompt=negative)
                return ("wan", task)
            except Exception as e:  # noqa: BLE001 — chain to happyhorse
                logger.warning("wan continuation failed (%s) — happyhorse", e)
        return ("happyhorse", await _happyhorse())

    async def _run_repair_step(self, step, *, project_id, shot, prompt, negative,
                               ratio, seed, ref_stack, frame_anchor, prev_clip_url,
                               role, source_clip_url):
        """Execute ONE repair strategy, returning (clip_url, used_tier) or
        (None, None). Never raises — a failed repair just yields nothing."""
        try:
            if step == "reseed":
                used_tier, task_id = await self._dispatch_by_role(
                    role=role, prompt=prompt, duration=shot.estimated_duration_seconds,
                    seed=(seed or 0) + 7, ratio=ratio, negative=negative,
                    ref_stack=ref_stack or None, frame_anchor=frame_anchor,
                    prev_clip_url=prev_clip_url)
            elif step == "reanchor":
                used_tier, task_id = await self._dispatch_by_role(
                    role="anchor", prompt=prompt, duration=shot.estimated_duration_seconds,
                    seed=(seed or 0) + 11, ratio=ratio, negative=negative,
                    ref_stack=ref_stack or None, frame_anchor=None,
                    prev_clip_url=None)
            elif step == "videoedit":
                media = (ref_stack or [])[:2]        # identity/costume plates
                if not media:
                    return (None, None)
                task_id = await self.qwen.generate_video_videoedit(
                    prompt=prompt, source_video_url=source_clip_url,
                    reference_media=media, duration=shot.estimated_duration_seconds,
                    seed=(seed or 0) + 13, negative_prompt=negative)
                used_tier = "videoedit"
            else:
                return (None, None)
            clip_url = await self.qwen.poll_video_task(task_id)
            clip_url = await asyncio.to_thread(
                persist_clip_url, project_id, f"repair_{shot.id}", clip_url)
            return (clip_url, used_tier)
        except Exception as e:  # noqa: BLE001 — repair is best-effort
            logger.warning("repair step %s failed for shot %s: %s", step, shot.id, e)
            return (None, None)

    async def _process_beat(self, beat, job, char_by_name, bible, scene_number,
                            prev_last_frame_url, scene_anchor_url=None,
                            prev_shot_type=None):
        """Render a conversation beat as ONE wan multi-shot clip, then write a
        clip row per shot sharing that url with proportional trims. Returns
        (last_frame_url, clip_url, spent_usd). On dispatch failure returns
        (None, None, 0.0) so the caller can fall back to per-shot rendering.

        SCOPED LIMITATION: a beat is dispatched via plain wan continuation and
        does NOT apply the identity-routing newcomer->r2v demotion, so a beat
        that OPENS on a face-locked newcomer with no established frame renders
        identity-blind. Acceptable today because multishot is opt-in and best
        used for continuation beats, not character introductions."""
        from app.services.multishot import multishot_prompt, slice_ranges
        from app.services.video_stitcher import VideoStitcher
        from app.services.guardrails import canonical_character
        pid = str(job.project_id)
        spent_usd = 0.0
        # resolve raw name variants ("Eirik" -> "Eirik Halden") before dedup, or
        # the continuity check mis-scores the beat exactly like _process_shot's
        in_frame = []
        for s in beat:
            for nm in (s.characters_in_frame or []):
                cn = canonical_character(nm, bible["characters"])
                if cn not in in_frame:
                    in_frame.append(cn)
        durations = [s.estimated_duration_seconds for s in beat]
        want = min(sum(durations), get_settings().multishot_max_duration)
        prompt = multishot_prompt(beat, durations)
        ratio = getattr(self, "_video_ratio", VIDEO_RATIO)
        seed = stable_seed(pid, beat[0].id)
        frame_anchor = prev_last_frame_url or scene_anchor_url
        media = [{"type": "first_frame", "url": frame_anchor}] if frame_anchor else None
        try:
            task_id = await self.qwen.generate_video_wan(
                prompt=prompt, duration=want, reference_media=media,
                seed=seed, ratio=ratio)
        except Exception as e:  # noqa: BLE001 — degrade to per-shot rendering
            logger.warning("multishot beat dispatch failed (%s) — falling back", e)
            return None, None, 0.0
        # Post-dispatch pipeline is fully guarded: a poll/probe/validate/write
        # failure returns (None, None, spent_usd) so the caller falls back to
        # per-shot rendering instead of crashing the whole scene.
        try:
            used_tier = "wan"
            clip_url = await self.qwen.poll_video_task(task_id)
            clip_url = await asyncio.to_thread(persist_clip_url, pid, f"beat_{beat[0].id}", clip_url)
            real_dur = VideoStitcher._duration(clip_url) or want
            guard = await self.continuity.validate(
                clip_url=clip_url, duration=real_dur, characters_in_frame=in_frame,
                bible=bible, scene_number=scene_number, foreground_characters=[])
            status = "APPROVED" if guard["overall_pass"] else "NEEDS_REVIEW"
            amt = record_video(self.db, pid, real_dur, used_tier)
            job.actual_cost += amt
            spent_usd += amt
            # the beat's closing frame doubles as EVERY beat clip's poster — a
            # resume run seeds the frame chain from an approved shot's poster,
            # so without it a shot after a beat loses continuity on resume
            frame_url = self._store_last_frame(pid, beat[-1], clip_url)
            ranges = slice_ranges(durations, real_dur)
            for s, (t0, t1) in zip(beat, ranges):
                self.db.add(GeneratedClip(
                    job_id=job.id, shot_id=s.id, model_used=used_tier, prompt=prompt,
                    url=clip_url, consistency_score=guard["continuity_score"],
                    face_score=guard.get("face_score"), outfit_score=guard.get("outfit_score"),
                    background_score=guard.get("background_score"),
                    seed=seed, status=status, trim_start=t0, trim_end=t1,
                    poster_url=frame_url))
                job.completed_shots += 1
            # the first non-empty poster names the drama's card (mirror _process_shot)
            if frame_url:
                try:
                    from app.models.project import Project
                    project = (self.db.query(Project)
                               .filter(Project.id == job.project_id).first())
                    if project and not project.poster_url:
                        project.poster_url = frame_url
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"beat poster persist skipped: {e}")
            self.db.commit()
            return frame_url, clip_url, spent_usd
        except Exception as e:  # noqa: BLE001 — never crash the scene; fall back to per-shot
            # roll back FIRST: a flush/commit failure (autoflush on the Project
            # query, or db.commit()) leaves the session inactive, and the
            # fallback's next _process_shot query would raise
            # PendingRollbackError — the exact crash the fallback exists to
            # prevent. Guard the rollback so a rollback error can't escape either.
            try:
                self.db.rollback()
            except Exception:  # noqa: BLE001
                pass
            logger.warning("multishot beat post-dispatch failed (%s) — "
                           "falling back to per-shot", e)
            return None, None, spent_usd

    async def _process_shot(self, job, shot, char_by_name, bible, scene_number,
                            prev_last_frame_url, scene_anchor_url=None,
                            scene_setting=None, suppress_location=False,
                            prev_action=None, next_action=None,
                            lipsync_line=None, environment=None,
                            prev_in_frame=None, prev_shot_type=None,
                            prev_clip_url=None):
        spent_usd = 0.0
        pid = str(job.project_id)
        # shots boarded before name normalization store raw variants ("Eirik"
        # for "Eirik Halden") — resolve against the cast HERE or the bible
        # lookups (outfits, identity refs, continuity) silently miss them
        from app.services.guardrails import canonical_character
        in_frame = [canonical_character(n, bible["characters"])
                    for n in (shot.characters_in_frame or [])]
        foreground = [canonical_character(n, bible["characters"])
                      for n in (getattr(shot, "foreground_characters", None) or [])]
        foreground = [n for n in foreground if n in in_frame]
        is_wan = shot.quality_tier == "wan"
        # wan2.7-i2v can only continue a face from the previous frame — it takes
        # NO identity references. A shot that INTRODUCES a face-locked character
        # (absent from the previous shot), or has no frame to continue from,
        # cannot get identity from wan. Live-measured on real dramas: wan2.7-r2v
        # holds a face far WORSE than happyhorse r2v (continuity ~46 vs ~67),
        # because happyhorse is reference-image native while wan's r2v is a
        # secondary mode. So identity-critical shots demote to happyhorse r2v,
        # which carries the full bible stack. wan keeps its real strength:
        # continuing a face already established in the last frame.
        frame_anchor_pre = prev_last_frame_url or scene_anchor_url
        settings_v2 = getattr(get_settings(), "identity_routing_v2", False)
        # Compute newcomers for EVERY tier, not just wan: under the v2 flag the
        # role block below runs for every shot, so a face-locked newcomer
        # entering on a non-wan shot must still be detected as an entrance.
        newcomers = []
        if prev_in_frame is not None:
            prev_set = {canonical_character(n, bible["characters"])
                        for n in (prev_in_frame or [])}
            newcomers = [n for n in in_frame
                         if n not in prev_set and n not in foreground
                         and any(v.get("plate_image_url")
                                 for v in (bible["characters"].get(n) or {}).get("variants", []))]
        if is_wan and (newcomers or not frame_anchor_pre):
            # only the LEGACY path demotes to happyhorse here; under v2 this same
            # shot routes to wan_r2v, so the "rendering there" claim would be false
            if not settings_v2:
                logger.info("shot %s needs a face reference (newcomers=%s, "
                            "no-frame=%s) — happyhorse r2v holds identity better "
                            "than wan, rendering there with the bible stack",
                            shot.id, newcomers, not frame_anchor_pre)
            is_wan = False
        role = None
        if settings_v2:
            from app.services.shot_roles import classify_shot_role, angle_changed
            has_locked_newcomer = bool(newcomers)
            role = classify_shot_role(
                has_frame_anchor=bool(frame_anchor_pre),
                has_locked_newcomer=has_locked_newcomer,
                is_angle_change=angle_changed(
                    prev_shot_type, shot.shot_type,
                    bool((getattr(shot, "blocking_json", None) or {}).get("reverse_angle"))))
            # continue_hold is the only role that stays on wan i2v — reangles
            # always go to the reference model (angle changes must not ride
            # continuation), so there is no same-cast demotion here.
            is_wan = role == "continue_hold"
        speaks = bool((shot.dialogue or "").strip())
        wan_primary_on = getattr(get_settings(), "wan_primary", False)
        # Where will _dispatch_by_role ACTUALLY send this shot? The [Image N]
        # legend and native talk must track the real target, not the role: wan
        # i2v/t2v attaches no reference images (a legend there describes phantom
        # pictures the model never receives), and a "says the line aloud" clause
        # can't be honored by a silent Wan visual. Computed once, mirrored from
        # the dispatch branches, so the prompt and the payload can't drift.
        if settings_v2 and wan_primary_on:
            to_happyhorse = (speaks or bool(newcomers) or role == "continue_reangle"
                             or (role == "anchor" and bool(in_frame)))
            refs_attached = to_happyhorse
        elif settings_v2:
            ref_native = role in ("anchor", "entrance", "continue_reangle")
            wan_r2v_native = (ref_native and getattr(
                get_settings(), "anchor_ref_model", "happyhorse") == "wan")
            to_happyhorse = ((ref_native and not wan_r2v_native)
                             or (role == "continue_hold" and getattr(
                                 get_settings(), "route_continuation_to_happyhorse", True)))
            # wan r2v still carries the plate stack, so the legend stays valid there
            refs_attached = ref_native or to_happyhorse
        else:
            to_happyhorse = not is_wan
            refs_attached = False   # the legend is v2-only
        model_cap = 5 if is_wan else 9
        if settings_v2 and role in ("anchor", "entrance", "continue_reangle"):
            # r2v takes <=5 media total; entrance/reangle also spend one slot on
            # first_frame, so leave room for it and the identity plates
            model_cap = 4 if role in ("entrance", "continue_reangle") else 5
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
        # [Image N] guide: tie each reference plate to its person so the model
        # never swaps faces/outfits across a multi-character shot. Only when the
        # dispatch target actually ATTACHES the stack (r2v paths) — a Wan i2v/t2v
        # shot must never carry a legend for images it is not sent. OFF -> "".
        image_legend = ""
        if (getattr(get_settings(), "image_ref_labels", False) and ref_stack
                and settings_v2 and refs_attached):
            from app.services.reference_stack import image_ref_legend
            image_legend = image_ref_legend(ref_provenance)

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
                # the native-talk decision comes BEFORE prompt crafting: a
                # native-talk shot is framed openly talking, every other spoken
                # line gets mouth-hiding coverage — the crafter needs to know which.
                frame_anchor = frame_anchor_pre if (is_wan or settings_v2) else None
                # HappyHorse native-talk: the model SPEAKS the line itself and
                # syncs its own mouth, so it works on MULTI-person shots too — we
                # NAME the speaker in the prompt so the right mouth moves and the
                # others stay closed. Fires on ANY shot that renders on
                # HappyHorse (to_happyhorse), not just ref-native roles — a
                # dialogue continuation routed there must still voice its line.
                # OFF by default -> byte-identical.
                # The model's own voice IS the delivered audio (no TTS overlay).
                # The script writes speaker names with stage qualifiers
                # ("DEOK-HYUN (O.S.)") — canonicalize BEFORE the in-frame check,
                # or the qualifier silently kills the line's voice.
                native_speaker = canonical_character(
                    str((lipsync_line or {}).get("character_name") or "").strip(),
                    bible["characters"])
                native_talk = (
                    getattr(get_settings(), "happyhorse_native_talk", False)
                    and settings_v2
                    and to_happyhorse
                    and attempt == 0
                    and get_settings().lipsync_enabled
                    and lipsync_line
                    and bool(native_speaker)
                    and native_speaker.upper() in {str(c).strip().upper() for c in in_frame})
                tool_event(pid, "generate", "prompt_craft", "started", agent="Director",
                           index=job.completed_shots + 1, total=job.total_shots)
                # Wan visual shot? The shared dispatch-target predicate: a shot
                # NOT bound for HappyHorse under wan_primary renders on Wan, so
                # the crafter appends Wan's SFX/ambience + no-dialogue/no-BGM
                # tail. OFF (wan_primary/v2 off) -> False -> byte-identical.
                to_wan = settings_v2 and wan_primary_on and not to_happyhorse
                crafted = await self._craft_prompt(
                    shot, char_by_name, scene_setting, prev_action, next_action,
                    foreground=foreground, outfits=outfits,
                    blocking=getattr(shot, "blocking_json", None),
                    native_talk=native_talk,
                    speaker=(native_speaker if native_talk else ""),
                    image_legend=image_legend, environment=environment,
                    to_wan=to_wan)
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
                # a wan-planned shot demoted to happyhorse (newcomer / no-frame)
                # must RECORD happyhorse, not its planned tier
                used_tier = ("happyhorse"
                             if (shot.quality_tier == "wan" and not is_wan)
                             else (shot.quality_tier or "happyhorse"))
                if settings_v2:
                    used_tier, task_id = await self._dispatch_by_role(
                        role=role, prompt=prompt, duration=shot.estimated_duration_seconds,
                        seed=seed, ratio=ratio, negative=negative,
                        ref_stack=ref_stack or None, frame_anchor=frame_anchor,
                        prev_clip_url=prev_clip_url,
                        speaks=bool((shot.dialogue or "").strip()),
                        has_newcomers=bool(newcomers),
                        has_faces=bool(in_frame))
                elif is_wan:
                    # wan2.7-i2v does NOT take identity references — its media
                    # schema is first_frame / last_frame / first_clip only. wan's
                    # job here is to CONTINUE the scene from the previous shot's
                    # last frame. is_wan is only still true for a CONTINUATION
                    # shot (a frame anchor exists and no locked-identity newcomer
                    # entered); identity-critical shots were demoted upstream. On
                    # failure it falls down the chain: first-frame -> happyhorse r2v.
                    task_id = None
                    if frame_anchor:
                        try:
                            task_id = await self.qwen.generate_video_wan(
                                prompt=prompt, duration=shot.estimated_duration_seconds,
                                reference_media=[{"type": "first_frame", "url": frame_anchor}],
                                seed=seed, ratio=ratio, negative_prompt=negative)
                        except Exception as we:  # noqa: BLE001 — chain to happyhorse
                            logger.warning("wan first-frame failed for shot %s (%s) — "
                                           "falling back to happyhorse r2v", shot.id, we)
                    if task_id is None:
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
                # snapshot the FIRST render's tier before any repair pass can
                # overwrite used_tier — the primary booking below always bills
                # this one render exactly once, no matter what the ladder does
                first_tier = used_tier
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
                # Bounded, budget-gated repair ladder: a soft continuity fail gets
                # a shot at reseed/reanchor/videoedit (cheapest first), keeping
                # whichever render scores best. OFF by default — a settings object
                # that doesn't define these (some tests substitute a bare
                # SimpleNamespace for an unrelated flag) is treated as repair-off,
                # not a crash, matching identity_routing_v2's getattr convention.
                if (getattr(get_settings(), "repair_enabled", False)
                        and not guard["overall_pass"]):
                    best_url, best_guard, best_tier = clip_url, guard, used_tier
                    renders_left = getattr(get_settings(), "repair_max_renders", 2)
                    for step in repair_steps(guard, role or "anchor", renders_left):
                        if renders_left <= 0 or getattr(self, "_cancelled", False):
                            break
                        renders_left -= 1
                        r_url, r_tier = await self._run_repair_step(
                            step, project_id=str(job.project_id), shot=shot,
                            prompt=prompt, negative=negative, ratio=ratio, seed=seed,
                            ref_stack=ref_stack, frame_anchor=frame_anchor,
                            prev_clip_url=prev_clip_url, role=role or "anchor",
                            source_clip_url=best_url)
                        if not r_url:
                            continue
                        r_amt = record_video(self.db, str(job.project_id),
                                             shot.estimated_duration_seconds, r_tier,
                                             ref_id=str(shot.id))
                        job.actual_cost += r_amt
                        spent_usd += r_amt
                        r_guard = await self.continuity.validate(
                            clip_url=r_url, duration=shot.estimated_duration_seconds,
                            characters_in_frame=in_frame, bible=bible,
                            scene_number=scene_number, foreground_characters=foreground)
                        if r_guard["continuity_score"] > best_guard["continuity_score"]:
                            best_url, best_guard, best_tier = r_url, r_guard, r_tier
                        if r_guard["overall_pass"]:
                            break
                    clip_url, guard, used_tier = best_url, best_guard, best_tier
                    status = "APPROVED" if guard["overall_pass"] else "NEEDS_REVIEW"
                    logger.info("repair for shot %s: best continuity %s (%s)",
                                shot.id, guard["continuity_score"], status)
                # Catastrophic render (black / empty / faceless) — always worth one
                # fresh-seed re-roll, independent of repair_enabled, so a dead frame
                # like a black Shot never ships flagged when a re-render could save
                # it. Bill the failed render (we paid for it), then re-loop with a
                # new seed. On the last attempt it falls through and ships flagged.
                if (attempt < MAX_RETRIES and not guard["overall_pass"]
                        and _is_catastrophic(guard, in_frame)):
                    bad_amt = record_video(self.db, str(job.project_id),
                                           shot.estimated_duration_seconds, used_tier,
                                           ref_id=str(shot.id))
                    job.actual_cost += bad_amt
                    spent_usd += bad_amt
                    logger.warning("shot %s render catastrophic (cont=%s face=%s bg=%s) "
                                   "— re-rolling with a fresh seed",
                                   shot.id, guard.get("continuity_score"),
                                   guard.get("face_score"), guard.get("background_score"))
                    tool_event(pid, "generate", "self_correct", "started", agent="Renderer",
                               index=attempt + 1, total=MAX_RETRIES, error="catastrophic render")
                    seed = seed + 7919   # a fresh seed so the re-render actually differs
                    continue
                # No TTS overlay now: the clip plays its own NATIVE audio at full
                # volume, so no bed/mute/onset policy is computed or stored.
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
                    status=status, retries=attempt)
                self.db.add(clip)
                job.completed_shots += 1
                self.db.commit()
                tool_event(pid, "generate", "write_clip_db", "succeeded", agent="Renderer",
                           artifact=f"{job.completed_shots} clip rows")
                if attempt > 0:
                    tool_event(pid, "generate", "self_correct", "succeeded",
                               agent="Renderer", artifact="recovered on retry")
                # the primary booking always bills the FIRST render exactly once —
                # the ladder above already billed any repair renders separately
                amt = record_video(self.db, str(job.project_id), shot.estimated_duration_seconds,
                                   first_tier, ref_id=str(clip.id))
                job.actual_cost += amt
                spent_usd += amt
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
                return (frame_url, clip_url, spent_usd)
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
                    return (None, None, spent_usd)
        return (None, None, spent_usd)
