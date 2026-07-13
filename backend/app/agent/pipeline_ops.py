"""Canonical pipeline stage operations shared by the LangGraph agent.

These mirror the per-stage HTTP routers but are callable directly by the
autonomous agent. Each takes a DB session and returns plain dicts.
"""
import uuid
from sqlalchemy.orm import Session
from app.models.script import Script, Scene
from app.models.character import Character
from app.models.shot import Shot
from app.models.generation_job import GenerationJob
from app.services.script_generator import ScriptGenerator
from app.services.script_structurer import ScriptStructurer
from app.services.character_extractor import CharacterExtractor
from app.services.storyboard_generator import StoryboardGenerator, plan_shot_budget
from app.services.guardrails import InputSanitizer
from app.mcp_tools.token_optimizer import TokenOptimizer
from app.graph.sync import sync_scenes, sync_characters
from app.websocket.emitter import emit
from app.websocket.tool_events import tool_event, tool_run


def _progress(pid, stage: str, status: str, agent: str, label: str, **extra) -> None:
    emit("stage:progress", {"stage": stage, "status": status,
                            "agent": agent, "label": label, **extra}, str(pid))


def _persist_script(db: Session, project_id: str, raw_text: str, structured: dict) -> tuple[Script, dict]:
    script = Script(project_id=uuid.UUID(project_id), raw_text=raw_text, structured_json=structured)
    db.add(script)
    db.flush()
    scene_uuids: dict = {}
    for sc in structured.get("scenes", []):
        scene = Scene(
            script_id=script.id,
            number=sc.get("scene_number", 0),
            title=sc.get("heading", ""),
            heading=sc.get("heading", ""),
            location=sc.get("location", ""),
            time_of_day=sc.get("time_of_day", ""),
            characters_json=sc.get("characters_present", []),
            description=sc.get("summary", ""),
            emotional_beat=sc.get("emotional_beat", ""),
            dialogue_json=sc.get("dialogue_lines", []),
            stage_directions=sc.get("stage_directions", []),
        )
        db.add(scene)
        scene_uuids[scene.number] = str(scene.id)
    db.commit()
    db.refresh(script)
    return script, scene_uuids


async def generate_script_op(
    db: Session, project_id: str, premise: str, genre: str,
    tone: str = "dramatic", episode_count: int = 1, target_length: int = 30,
    language: str = "en", notes: str = "", model: str | None = None,
) -> dict:
    from app.services.usage_tracker import track_project
    _progress(project_id, "script", "started", "Screenwriter",
              "Rewriting with the judge's notes" if notes else "Writing your screenplay")
    with track_project(project_id, db):
        clean_premise = InputSanitizer().sanitize(premise, max_length=300)
        with tool_run(project_id, "script", "llm_write", "Screenwriter") as t:
            raw_text = await ScriptGenerator().generate(
                genre=genre, premise=clean_premise, tone=tone,
                episode_count=episode_count, target_length=target_length, language=language,
                notes=notes, model=model or "qwen-max",
            )
            t["artifact"] = "1 draft"
        _progress(project_id, "script", "update", "Screenwriter", "Structuring scenes and beats")
        with tool_run(project_id, "script", "structure_scenes", "Screenwriter") as t:
            structured = await ScriptStructurer().structure(raw_text, language=language)
            t["artifact"] = f"{len(structured.get('scenes', []))} scenes"
        with tool_run(project_id, "script", "write_script_db", "Screenwriter") as t:
            script, scene_uuids = _persist_script(db, project_id, raw_text, structured)
            t["artifact"] = f"{len(scene_uuids)} rows"
        sync_scenes(project_id, structured, scene_uuids=scene_uuids)
        # Full Auto enters the premise here, not at create time — reflect it on
        # the project so the dashboard card and chat context stay truthful, and
        # name an untitled drama from it.
        try:
            from app.models.project import Project
            project = db.query(Project).filter(Project.id == uuid.UUID(project_id)).first()
            if project is not None and clean_premise:
                project.premise = clean_premise
                project.genre = genre or project.genre
                if (project.title or "").strip().lower() in ("", "untitled drama"):
                    try:
                        from app.routers.projects import _clean_title, _llm_title
                        suggested = _clean_title(await _llm_title(clean_premise))
                        if suggested:
                            project.title = suggested
                    except Exception:  # noqa: BLE001
                        pass
                db.commit()
        except Exception:  # noqa: BLE001
            pass
        _progress(project_id, "script", "completed", "Screenwriter",
                  f"Script ready: {len(structured.get('scenes', []))} scene(s)")
        return {"script_id": str(script.id), "structured": structured}


async def extract_characters_op(db: Session, script_id: str, infer_mbti: bool = False) -> list[dict]:
    script = db.query(Script).filter(Script.id == uuid.UUID(script_id)).first()
    if not script or not script.structured_json:
        return []
    from app.services.usage_tracker import track_project
    _progress(script.project_id, "characters", "started", "Casting Director",
              "Reading the cast from the script")
    with track_project(script.project_id, db):
        with tool_run(script.project_id, "characters", "extract_cast", "Casting Director") as t:
            data = await CharacterExtractor().extract(script.structured_json)
            t["artifact"] = f"{len(data)} characters"
    tool_event(script.project_id, "characters", "write_cast_db", "started",
               agent="Casting Director")
    db.query(Character).filter(Character.project_id == script.project_id).delete()
    created = []
    for cd in data:
        c = Character(
            project_id=script.project_id, name=cd.get("name", "Unknown"),
            role=cd.get("role"), gender=cd.get("gender"),
            estimated_age=cd.get("estimated_age"),
            physical_description=cd.get("physical_description"),
            personality_summary=cd.get("personality_summary"),
            speech_pattern=cd.get("speech_pattern"),
            emotional_arc=cd.get("emotional_arc"),
            visual_description=cd.get("physical_description") or "",
            video_prompt_fragment=cd.get("physical_description") or "",
        )
        db.add(c)
        created.append(c)
    db.commit()
    for c in created:
        db.refresh(c)
    tool_event(script.project_id, "characters", "write_cast_db", "succeeded",
               agent="Casting Director", artifact=f"{len(created)} rows")
    sync_characters(str(script.project_id), created, script.structured_json)
    _progress(script.project_id, "characters", "completed", "Casting Director",
              f"{len(created)} character(s) cast")
    return [{"id": str(c.id), "name": c.name, "role": c.role} for c in created]


async def generate_storyboard_op(db: Session, script_id: str, target_length: int = 30) -> list[dict]:
    script = db.query(Script).filter(Script.id == uuid.UUID(script_id)).first()
    if not script:
        return []
    scenes = db.query(Scene).filter(Scene.script_id == script.id).order_by(Scene.number).all()
    characters = db.query(Character).filter(Character.project_id == script.project_id).all()
    char_map = {c.name.upper(): {"name": c.name, "role": c.role, "visual_description": c.visual_description or ""} for c in characters}

    scene_ids = [s.id for s in scenes]
    db.query(Shot).filter(Shot.scene_id.in_(scene_ids)).delete(synchronize_session=False)

    shots_per_scene, shot_seconds = plan_shot_budget(len(scenes), target_length)
    gen = StoryboardGenerator()
    created: list[tuple[Shot, int]] = []
    from app.services.usage_tracker import track_project
    _progress(script.project_id, "storyboard", "started", "Director",
              "Breaking the script into shots")
    dressed = 0
    with track_project(script.project_id, db):
        for scene_index, scene in enumerate(scenes, start=1):
            _progress(script.project_id, "storyboard", "update", "Director",
                      f"Scene {scene.number}: staging shots and set dressing",
                      index=scene_index, total=len(scenes))
            scene_chars = [char_map.get(str(n).upper(), {"name": n}) for n in (scene.characters_json or [])]
            # ── narrative memory READ: before staging this scene, the Director
            # recalls everything the story has already established (Neo4j) ──
            from app.graph.sync import recall_facts_before_scene, sync_scene_facts
            tool_event(script.project_id, "storyboard", "memory_recall", "started",
                       agent="Director", index=scene_index, total=len(scenes))
            established = recall_facts_before_scene(str(script.project_id), scene.number)
            tool_event(script.project_id, "storyboard", "memory_recall", "succeeded",
                       agent="Director",
                       artifact=(f"{len(established)} facts recalled" if established
                                 else "no prior facts"))
            tool_event(script.project_id, "storyboard", "shot_breakdown", "started",
                       agent="Director", index=scene_index, total=len(scenes))
            shots = await gen.generate_for_scene(
                {"scene_number": scene.number, "heading": scene.heading,
                 "description": scene.description, "emotional_beat": scene.emotional_beat,
                 # the scripted lines: the generator distributes them onto shots so
                 # has_dialogue is REAL — the audio-first duration fitter and voice
                 # placement both key on it. Omitting this left every full-auto
                 # shot silent on paper while the scene still talked.
                 "dialogue": scene.dialogue_json or [],
                 # what earlier scenes established — shots must not contradict it
                 "established_facts": established},
                scene_chars,
                max_shots=shots_per_scene,
                shot_seconds=shot_seconds,
            )
            # the 180-degree rule, enforced not requested: first placement
            # establishes each character's screen side; drift snaps back,
            # a flagged reverse angle re-establishes the line of action.
            # Subjects are normalized FIRST — the model sometimes returns
            # bare name strings instead of the structured dicts.
            from app.services.stage_map import enforce_scene_sides, normalize_subjects
            for sd in shots:
                if isinstance(sd, dict):
                    sd["subjects"] = normalize_subjects(sd.get("subjects"))
            _, _side_notes = enforce_scene_sides(
                [{"subjects": sd.get("subjects"),
                  "reverse_angle": bool(sd.get("reverse_angle"))}
                 if sd.get("subjects") else None for sd in shots])
            if _side_notes:
                import logging
                logging.getLogger(__name__).info(
                    "stage map corrections scene %s: %s", scene.number, _side_notes)
            # set dressing: pins props + prop state per scene (enhancement only)
            try:
                from app.services.set_dresser import SetDresser
                tool_event(script.project_id, "storyboard", "set_design", "started",
                           agent="Director", index=scene_index, total=len(scenes))
                scene.set_json = await SetDresser().dress(
                    {"scene_number": scene.number, "heading": scene.heading,
                     "location": scene.location, "description": scene.description,
                     "stage_directions": scene.stage_directions or []},
                    [{"shot_number": sd.get("shot_number"), "action": sd.get("action"),
                      "dialogue": sd.get("dialogue")} for sd in shots])
                dressed += 1
                # ── narrative memory WRITE: prop-state changes become Facts,
                # known by everyone in the scene — recalled by later scenes ──
                sync_scene_facts(
                    str(script.project_id), scene.number,
                    (scene.set_json or {}).get("state_changes") or [],
                    [c.get("name") for c in scene_chars if c.get("name")])
            except Exception:  # noqa: BLE001
                pass
            for sd in shots:
                # resolve name variants the LLM invents ("KERRY (ON SCREEN)")
                # back to real cast members, or identity references and the
                # pre-generation check never find them
                from app.services.guardrails import canonical_character
                known_names = [c.get("name") for c in scene_chars if c.get("name")]
                in_frame = list(dict.fromkeys(
                    canonical_character(n, known_names)
                    for n in (sd.get("characters_in_frame", []) or [])))
                # foreground names must be a subset of who is actually in frame
                foreground = [n for n in (canonical_character(x, known_names)
                                          for x in (sd.get("foreground_characters") or []))
                              if n in in_frame]
                # blocking subjects carry names too — the camera plan and the
                # prompt's blocking rows must show the same cast the shot lists
                for subj in (sd.get("subjects") or []):
                    if isinstance(subj, dict) and subj.get("character"):
                        subj["character"] = canonical_character(subj["character"], known_names)
                shot = Shot(
                    scene_id=scene.id, number=sd.get("shot_number", 1),
                    shot_type=sd.get("shot_type"), camera_movement=sd.get("camera_movement"),
                    lighting=sd.get("lighting"), colour_mood=sd.get("colour_mood"),
                    action=sd.get("action"), dialogue=sd.get("dialogue"),
                    emotional_beat=sd.get("emotional_beat"),
                    estimated_duration_seconds=sd.get("estimated_duration_seconds", 5),
                    characters_in_frame=in_frame,
                    foreground_characters=foreground,
                    blocking_json=({"subjects": sd.get("subjects"),
                                    "reverse_angle": bool(sd.get("reverse_angle"))}
                                   if sd.get("subjects") else None),
                    notes=sd.get("notes"),
                )
                db.add(shot)
                created.append((shot, scene.number))
    tool_event(script.project_id, "storyboard", "shot_breakdown", "succeeded",
               agent="Director", artifact=f"{len(created)} shots")
    tool_event(script.project_id, "storyboard", "set_design", "succeeded",
               agent="Director", artifact=f"{dressed} scenes dressed")
    with tool_run(script.project_id, "storyboard", "write_shots_db", "Director") as t:
        db.commit()
        t["artifact"] = f"{len(created)} rows"
    # Location plates ride along, exactly like the manual storyboard path:
    # the scenes exist now, so every location gets its background image here
    # instead of waiting for the user to press Generate Plates. Idempotent
    # and an enhancement only — never fails the storyboard.
    try:
        from app.services.casting_director import ensure_location_plates
        _progress(script.project_id, "storyboard", "update", "Director",
                  "Painting location plates")
        with track_project(script.project_id, db):
            await ensure_location_plates(db, script.project_id)
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning(
            "location plate generation failed after storyboard", exc_info=True)
    _progress(script.project_id, "storyboard", "completed", "Director",
              f"Storyboard ready: {len(created)} shots across {len(scenes)} scene(s)")
    # scene_number + shot_number ride along so the budget allocator can
    # protect the hook (the opening shots of scene 1) when it fits the plan
    # to the spend cap.
    return [{"shot_id": str(s.id), "shot_type": s.shot_type,
             "shot_number": s.number,
             "scene_number": scene_no,
             "emotional_beat": s.emotional_beat,
             "characters_in_frame": s.characters_in_frame or [],
             "dialogue": s.dialogue,
             "estimated_duration_seconds": s.estimated_duration_seconds}
            for s, scene_no in created]


def allocate_budget_op(db: Session, project_id: str, shots: list[dict], budget_usd: float | None = None) -> dict:
    if budget_usd is None:
        from app.models.project import Project
        project = db.query(Project).filter(Project.id == uuid.UUID(str(project_id))).first()
        budget_usd = float(project.credit_budget) if project and project.credit_budget else 40.0
    with tool_run(project_id, "generate", "budget_allocate", "Producer") as t:
        result = TokenOptimizer().allocate(shots, budget_usd)
        tier_by_id = {s["shot_id"]: s["quality_tier"] for s in result["scored_shots"]}
        for sid, tier in tier_by_id.items():
            shot = db.query(Shot).filter(Shot.id == uuid.UUID(sid)).first()
            if shot:
                shot.quality_tier = tier
        db.commit()
        t["artifact"] = f"{len(tier_by_id)} shots fitted"
    from app.agents.reporter import report_agent
    report_agent(db, project_id, agent="budget_allocator", stage="budget",
                 decision={"wan": result.get("wan_shots"), "happyhorse": result.get("happyhorse_shots")}
                         if isinstance(result, dict) else {},
                 rationale="Allocated quality tiers under the cap", confidence=1.0)
    # Tell the chat what fitting cost the plan, so the user can decide to
    # raise the cap instead of losing shots.
    if result.get("deferred_shots") or result.get("downgraded_shots"):
        import math
        emit("budget:fitted", {
            "deferred": result.get("deferred_shots", 0),
            "downgraded": result.get("downgraded_shots", 0),
            "cap": result.get("budget_usd", budget_usd),
            "suggested_cap": math.ceil(
                (result.get("unfitted_cost_usd", 0) or 0) / (1 - TokenOptimizer.RESERVE_PCT) + 0.999),
        }, str(project_id))
    return result


async def cast_bible_op(db: Session, project_id: str) -> dict:
    from app.services.casting_director import CastingDirector
    return await CastingDirector(db).cast_bible(project_id)


async def synth_dialogue_op(db: Session, project_id: str,
                            only_characters: set | None = None) -> int:
    """Synthesize dialogue audio. only_characters restricts the run to those
    speakers' lines (recast after first synthesis) — other characters' existing
    audio is left untouched."""
    from app.services.dialogue_synthesizer import DialogueSynthesizer
    from app.models.script import Script, Scene
    from app.models.character import Character
    from app.models.line_audio import LineAudio
    script = (db.query(Script).filter(Script.project_id == uuid.UUID(str(project_id)))
              .order_by(Script.created_at.desc()).first())
    if not script:
        return 0
    scenes = db.query(Scene).filter(Scene.script_id == script.id).order_by(Scene.number).all()
    chars = db.query(Character).filter(Character.project_id == uuid.UUID(str(project_id))).all()
    # Assign a distinct preset voice to any character that skipped casting, so the
    # export isn't every character speaking in the same fallback voice.
    from app.services.casting_director import assign_voice
    changed = False
    for i, c in enumerate(chars):
        if not c.voice_id:
            assign_voice(c, i, db=db, project_id=str(project_id))
            changed = True
    if changed:
        db.commit()
    voice_by_name = {c.name: {"voice_id": c.voice_id, "voice_model": c.voice_model} for c in chars}
    scene_dicts = [{"number": s.number, "dialogue_json": s.dialogue_json} for s in scenes]
    rows = await DialogueSynthesizer(db).synthesize_lines(
        project_id, scene_dicts, voice_by_name, only_characters=only_characters)
    # Exact replace: drop ONLY the (scene, line) slots we actually re-synthesized.
    # A line whose TTS failed keeps its previous audio instead of going silent,
    # and the next export's missing/stale detection retries it.
    new_keys = {(r["scene_number"], r["line_index"]) for r in rows}
    if new_keys:
        for old in db.query(LineAudio).filter(
                LineAudio.project_id == uuid.UUID(str(project_id))).all():
            if (old.scene_number, old.line_index) in new_keys:
                db.delete(old)
    for r in rows:
        db.add(LineAudio(**r))
    db.commit()
    from app.agents.reporter import report_agent
    report_agent(db, project_id, agent="audio_continuity", stage="audio",
                 decision={"lines": len(rows)},
                 rationale=f"Synthesized {len(rows)} dialogue lines", confidence=1.0)
    return len(rows)


async def clarify_op(db: Session, project_id: str) -> dict:
    from app.agents.clarification_agent import ClarificationAgent, needs_pause
    from app.agents.reporter import report_agent
    from app.models.project import Project
    from app.models.script import Script
    from app.models.character import Character
    from app.websocket.emitter import emit
    script = (db.query(Script).filter(Script.project_id == uuid.UUID(str(project_id)))
              .order_by(Script.created_at.desc()).first())
    chars = db.query(Character).filter(Character.project_id == uuid.UUID(str(project_id))).all()
    from app.services.usage_tracker import track_project
    with track_project(project_id, db):
        assessment = await ClarificationAgent().assess(
            (script.structured_json if script else {}) or {},
            [{"name": c.name, "physical_description": c.physical_description} for c in chars])
    project = db.query(Project).filter(Project.id == uuid.UUID(str(project_id))).first()
    pause = needs_pause(assessment, bool(project.auto_clarify) if project else False)
    report_agent(db, project_id, agent="clarification", stage="clarify",
                 decision=assessment,
                 rationale=("awaiting user answers" if pause else "no blocking ambiguity / auto-assumed"),
                 confidence=assessment.get("confidence", 1.0))
    if pause:
        emit("clarification.awaiting", {"questions": assessment["ambiguities"]}, str(project_id))
    return {"pause": pause, "assessment": assessment}


def dispatch_generation_op(db: Session, project_id: str, auto_export: bool = False) -> str:
    # auto_export: full-auto runs render the final episode as soon as the last
    # clip lands — one premise in, one finished MP4 out, zero clicks between.
    job = GenerationJob(project_id=uuid.UUID(project_id), auto_export=auto_export)
    db.add(job)
    db.commit()
    db.refresh(job)
    # instant feedback: the worker's own first event can be seconds away
    _progress(project_id, "generate", "started", "Showrunner",
              "Dispatching the render crew")
    from app.workers.generation_worker import run_generation_job
    run_generation_job.delay(str(job.id))
    return str(job.id)
