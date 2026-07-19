"""Canonical pipeline stage operations shared by the LangGraph agent.

These mirror the per-stage HTTP routers but are callable directly by the
autonomous agent. Each takes a DB session and returns plain dicts.
"""
import uuid
from sqlalchemy.orm import Session
from app.models.script import Script, Scene
from app.models.character import Character
from app.models.shot import Shot, clamp_bounded_strings
from app.models.generation_job import GenerationJob
from app.services.script_generator import ScriptGenerator
from app.services.script_structurer import ScriptStructurer
from app.services.character_extractor import CharacterExtractor
from app.services.storyboard_generator import (
    StoryboardGenerator, plan_shot_budget, plan_hold_budget)
from app.services.guardrails import InputSanitizer
from app.mcp_tools.token_optimizer import TokenOptimizer
from app.graph.sync import sync_scenes, sync_characters
from app.websocket.emitter import emit
from app.websocket.tool_events import tool_event, tool_run
from app.config import get_settings
from app.director.director import plan_scene
from app.director.recommender import recommend_look


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
        from app.services.guardrails import PREMISE_MAX
        clean_premise = InputSanitizer().sanitize(premise, max_length=PREMISE_MAX)
        # writers'-room development before the script — first write only, not
        # a judge-note revision (the story is already shaped by then)
        development = ""
        if not (notes or "").strip():
            from app.services.story_developer import StoryDeveloper
            with tool_run(project_id, "script", "develop_story", "Screenwriter") as t:
                treatment = await StoryDeveloper().develop(
                    premise=clean_premise, genre=genre, tone=tone,
                    episode_count=episode_count, language=language)
                development = StoryDeveloper.as_brief(treatment)
                t["artifact"] = StoryDeveloper.headline(treatment)
        with tool_run(project_id, "script", "llm_write", "Screenwriter") as t:
            raw_text = await ScriptGenerator().generate(
                genre=genre, premise=clean_premise, tone=tone,
                episode_count=episode_count, target_length=target_length, language=language,
                notes=notes, model=model or "qwen-max", development=development,
            )
            t["artifact"] = "1 draft"
        _progress(project_id, "script", "update", "Screenwriter", "Structuring scenes and beats")
        with tool_run(project_id, "script", "structure_scenes", "Screenwriter") as t:
            structured = await ScriptStructurer().structure(raw_text, language=language)
            t["artifact"] = f"{len(structured.get('scenes', []))} scenes"
        # dialogue-budget ENFORCEMENT: the prompt states the budget, but the
        # writer overshoots it 2x when the story wants more (11 lines on a 30s
        # ask boarded 73s). ONE trim rewrite with a judge-style note; a draft
        # still over after that proceeds — boarding's over-target warning
        # surfaces it before render money is spent.
        from app.services.script_generator import (
            over_line_budget, count_dialogue_lines, trim_note)
        budget = over_line_budget(structured, target_length)
        if budget is not None:
            n_lines = count_dialogue_lines(structured)
            _progress(project_id, "script", "update", "Screenwriter",
                      f"Draft runs long ({n_lines} lines), trimming to {budget}")
            with tool_run(project_id, "script", "trim_dialogue", "Screenwriter") as t:
                raw_text = await ScriptGenerator().generate(
                    genre=genre, premise=clean_premise, tone=tone,
                    episode_count=episode_count, target_length=target_length,
                    language=language, notes=trim_note(n_lines, budget, target_length),
                    model=model or "qwen-max", development=development,
                )
                structured = await ScriptStructurer().structure(raw_text, language=language)
                t["artifact"] = f"{count_dialogue_lines(structured)} lines"
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
            # the script's own prose decides the language — the run request's
            # language never reached this op, so zh casts extracted half-blind
            from app.services.language import detect_language
            data = await CharacterExtractor().extract(
                script.structured_json, language=detect_language(script.raw_text))
            t["artifact"] = f"{len(data)} characters"
    tool_event(script.project_id, "characters", "write_cast_db", "started",
               agent="Casting Director")
    db.query(Character).filter(Character.project_id == script.project_id).delete()
    # A generic placeholder ('UNKNOWN FIGURE', 'Man', 'their brother', 'Guard 2')
    # must NEVER be cast: it has no real identity to lock, renders as garbled
    # text, and pollutes the cast. Drop it here and surface which ones — the
    # figure stays in the action text as a generic extra.
    from app.services.guardrails import drop_placeholder_characters
    data, dropped = drop_placeholder_characters(data)
    if dropped:
        import logging
        logging.getLogger(__name__).warning(
            "dropped placeholder cast names (not cast): %s", dropped)
        emit("characters:placeholders_dropped",
             {"names": dropped}, str(script.project_id))
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
    # drama-level atmosphere budget for wan_beats: faceless scenery cutaways,
    # ~1 per 35s with a floor of 1 (even a short piece gets a breath) and a cap
    # of 3. Decremented as scenes consume it — a single-scene drama spends the
    # whole budget in that scene (spaced out).
    atmo_budget = min(3, max(1, round((target_length or 0) / 35)))
    # drama-level held-beat budget (~1 per 45s, cap 2) and the look the last
    # hold used, threaded across scenes so wording never repeats drama-wide
    hold_budget = plan_hold_budget(target_length)
    hold_variant = -1
    with track_project(script.project_id, db):
        for scene_index, scene in enumerate(scenes, start=1):
            _progress(script.project_id, "storyboard", "update", "Director",
                      f"Scene {scene.number}: staging shots and set dressing",
                      index=scene_index, total=len(scenes))
            scene_chars = [char_map.get(str(n).upper(), {"name": n}) for n in (scene.characters_json or [])]
            # The structurer's characters_present drops on-screen pets and
            # object-like names (雪球 = "snowball") — leaving them out of every
            # shot AND letting the set dresser mistake the pet for a prop. Add
            # back any real cast member NAMED in the scene's own prose (CJK-safe).
            from app.services.stage_map import cast_named_in_prose
            _scene_prose = " ".join(str(x) for x in
                                    ([scene.description or ""] + list(scene.stage_directions or [])))
            scene_chars = cast_named_in_prose(scene_chars, list(char_map.values()), _scene_prose)
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
            scene_json = {
                "scene_number": scene.number, "heading": scene.heading,
                "description": scene.description, "emotional_beat": scene.emotional_beat,
                # the scripted lines: the generator distributes them onto shots so
                # has_dialogue is REAL — the audio-first duration fitter and voice
                # placement both key on it. Omitting this left every full-auto
                # shot silent on paper while the scene still talked.
                "dialogue": scene.dialogue_json or [],
                # what earlier scenes established — shots must not contradict it
                "established_facts": established,
            }
            if getattr(get_settings(), "director_engine", False):
                try:
                    # genre lives on Project (Script has none); safe on a detached
                    # Script. Budget = one shot per line PLUS non-verbal beats
                    # granted by the TIME budget (a flat +2 let a 30s drama board
                    # 8 silent beats). Capped at 12.
                    genre = getattr(getattr(script, "project", None), "genre", None)
                    n_lines = len(scene.dialogue_json or [])
                    from app.services.storyboard_generator import plan_scene_shot_budget
                    budget = plan_scene_shot_budget(shots_per_scene, n_lines, gen._HARD_CAP)
                    look = recommend_look(genre)
                    plan = await plan_scene(scene_json, scene_chars, look,
                                            budget=budget, qwen=gen.qwen)
                    shots = await gen.stage_plan(scene_json, scene_chars, plan)
                except Exception as e:  # noqa: BLE001 — Director is best-effort
                    import logging
                    logging.getLogger(__name__).warning(
                        "Director pass failed for scene %s, falling back: %s", scene.number, e)
                    shots = await gen.generate_for_scene(
                        scene_json, scene_chars, max_shots=shots_per_scene, shot_seconds=shot_seconds)
            else:
                shots = await gen.generate_for_scene(
                    scene_json, scene_chars, max_shots=shots_per_scene, shot_seconds=shot_seconds)
            # Wan enrichment (all deterministic, flag-gated; OFF -> byte-identical).
            # A helper renumbers the scene only when a shot was actually inserted.
            enriched = False
            # all-speech boarding: every shot carries a line (silent beats
            # teleported postures and read as filler)
            if getattr(get_settings(), "dialogue_only", False):
                from app.services.storyboard_generator import drop_silent_shots
                shots, dropped_n = drop_silent_shots(shots)
                if dropped_n:
                    enriched = True
            # people-free scenery disallowed (wan_atmosphere off): drop even the
            # Director's own — empty Wan scenes render square and hallucinate,
            # and they read as disconnected from the drama
            if not getattr(get_settings(), "wan_atmosphere", False):
                from app.services.storyboard_generator import drop_scenery_shots
                shots, dropped_n = drop_scenery_shots(shots)
                if dropped_n:
                    enriched = True
            _look_of = lambda key: next((sd.get(key) for sd in shots if sd.get(key)), None)
            # (1) Guarantee a Wan visual WITHOUT burying the hook: the drama's
            # first 3 seconds belong to the most arresting beat, so the
            # establishing wide slots in at the first safe boundary AFTER the
            # hook (never splitting a question from its answer), and a scenery
            # opener the Director boarded itself is relocated the same way.
            if (scene_index == 1
                    and getattr(get_settings(), "ensure_establishing_shot", False)):
                from app.services.storyboard_generator import hook_first_scenery
                shots, hook_action = hook_first_scenery(
                    shots, scene.location, _look_of("lighting"), _look_of("colour_mood"))
                if hook_action:
                    enriched = True
                if hook_action == "inserted":
                    # a NEW establishing wide IS one scenery beat — count it
                    # against the atmosphere budget so scene 1 doesn't pile up
                    # cutaways (a relocation adds nothing, so it costs nothing)
                    atmo_budget = max(0, atmo_budget - 1)
            # (2) Weave silent Wan beats: held two-shots between dialogue (same
            # framing + cast, no line -> Wan continuation), and a few faceless
            # atmosphere cutaways drawn from the drama-level budget.
            if getattr(get_settings(), "wan_beats", False):
                from app.services.storyboard_generator import (
                    insert_silent_holds, insert_atmosphere)
                if hold_budget > 0:
                    held, hold_variant = insert_silent_holds(
                        shots, max_holds=hold_budget, last_variant=hold_variant)
                    if len(held) != len(shots):
                        hold_budget -= len(held) - len(shots)
                        shots, enriched = held, True
                if atmo_budget > 0 and getattr(get_settings(), "wan_atmosphere", False):
                    before = len(shots)
                    with_atmo = insert_atmosphere(shots, atmo_budget, scene.location,
                                                  _look_of("lighting"),
                                                  _look_of("colour_mood"))
                    inserted = len(with_atmo) - before
                    if inserted > 0:
                        shots, enriched = with_atmo, True
                        atmo_budget -= inserted
            # (3) Room lock: a scene that OPENS tight (the hook) gets a brief
            # silent wide right after it, so later shots chain from real
            # pixels of the established room instead of only the painted plate
            if getattr(get_settings(), "reorient_wide", False):
                from app.services.storyboard_generator import insert_reorient_wide
                widened = insert_reorient_wide(shots, scene.location)
                if len(widened) != len(shots):
                    shots, enriched = widened, True
            if enriched:
                for idx, sd in enumerate(shots, start=1):
                    sd["shot_number"] = idx
            # the 180-degree rule, enforced not requested: first placement
            # establishes each character's screen side; drift snaps back,
            # a flagged reverse angle re-establishes the line of action.
            # Subjects are normalized FIRST — the model sometimes returns
            # bare name strings instead of the structured dicts.
            from app.services.stage_map import (
                enforce_barrier_depth, enforce_proximity, enforce_scene_sides,
                normalize_subjects, thread_held_objects)
            for sd in shots:
                if isinstance(sd, dict):
                    sd["subjects"] = normalize_subjects(sd.get("subjects"))
            _blk = [{"subjects": sd.get("subjects"),
                     "reverse_angle": bool(sd.get("reverse_angle"))}
                    if sd.get("subjects") else None for sd in shots]
            _, _side_notes = enforce_scene_sides(_blk)
            # a carried prop (a birdcage, a phone) must stay in hand across the
            # scene's shots — held state lived only in each shot's free text, so
            # a shot that omitted it dropped the object; thread it forward.
            _, _held_notes = thread_held_objects(_blk)
            # a character SEEN THROUGH a fence/window stands on its far side:
            # staged deep background beyond the barrier (threaded across the
            # scene until a crossing), never beside the onlookers. Runs after
            # the depth-snap pass (which would overwrite the far-side string)
            # and BEFORE proximity, which must not pair a barrier-separated duo.
            _, _barrier_notes = enforce_barrier_depth(shots)
            # you cannot walk toward someone you are already with: an approach
            # aimed at an established scene partner is a teleport-reset the
            # board wrote by accident — rewritten to stand with them.
            _, _prox_notes = enforce_proximity(shots)
            # a pet tied to an anchor stays tied shot after shot (the rope
            # rendered unattached when the tie lived in one shot's prose),
            # and a grab already made continues as a hold instead of being
            # re-performed with an awkward re-approach
            from app.services.stage_map import (continue_restated_contact,
                                                thread_anchors, thread_tethered)
            _, _tether_notes = thread_tethered(shots)
            _, _anchor_notes = thread_anchors(shots)
            _, _grip_notes = continue_restated_contact(shots)
            _all_notes = (_side_notes + _held_notes + _prox_notes
                          + _barrier_notes + _tether_notes + _anchor_notes
                          + _grip_notes)
            if _all_notes:
                import logging
                logging.getLogger(__name__).info(
                    "stage map corrections scene %s: %s", scene.number,
                    _all_notes)
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
                      "dialogue": sd.get("dialogue")} for sd in shots],
                    # the cast (incl. the pet) must never be dressed as a prop
                    cast_names=[c.get("name") for c in scene_chars if c.get("name")])
                dressed += 1
                # ── narrative memory WRITE: prop-state changes become Facts,
                # known by everyone in the scene — recalled by later scenes ──
                sync_scene_facts(
                    str(script.project_id), scene.number,
                    (scene.set_json or {}).get("state_changes") or [],
                    [c.get("name") for c in scene_chars if c.get("name")])
            except Exception:  # noqa: BLE001
                pass
            # real cast = the plated Characters. An EXTRA (background figure,
            # animal, one-time unnamed person) has no plate, so it must never
            # enter characters_in_frame / subjects: the router and reference
            # stack would chase an identity that cannot exist. A dropped extra
            # stays in the action text and renders as a generic figure.
            real_cast = {str(c.name).upper() for c in characters}
            from app.services.guardrails import canonical_character
            from app.services.stage_map import reconcile_frame_with_subjects
            known_names = [c.get("name") for c in scene_chars if c.get("name")]
            for sd in shots:
                # resolve name variants the LLM invents ("KERRY (ON SCREEN)")
                # back to real cast members, or identity references and the
                # pre-generation check never find them.
                # canonicalize against the SCENE cast (disambiguates bare first
                # names / stage qualifiers), then keep only real cast members
                in_frame = list(dict.fromkeys(
                    n for n in (canonical_character(x, known_names)
                                for x in (sd.get("characters_in_frame", []) or []))
                    if str(n).upper() in real_cast))
                # blocking subjects carry names too — canonicalize, then drop any
                # extra so the camera plan and the prompt's blocking rows never
                # reference a non-cast figure
                kept_subjects = []
                for subj in (sd.get("subjects") or []):
                    if isinstance(subj, dict) and subj.get("character"):
                        subj["character"] = canonical_character(subj["character"], known_names)
                        if str(subj["character"]).upper() not in real_cast:
                            continue
                    kept_subjects.append(subj)
                sd["subjects"] = kept_subjects or None
                # reconcile the frame with the blocking: a character listed
                # in-frame but never given a subject AND not named in the action
                # is a spurious inclusion the stager left unplaced (the antagonist
                # 'Man' in a two-person beat). Drop them so their plate isn't sent
                # as a floating face reference the model places at random.
                in_frame = reconcile_frame_with_subjects(
                    in_frame, kept_subjects, sd.get("action"))
                sd["characters_in_frame"] = in_frame
                # foreground names must be a subset of who is actually in frame
                sd["foreground_characters"] = [
                    n for n in (canonical_character(x, known_names)
                                for x in (sd.get("foreground_characters") or []))
                    if n in in_frame]
            # a character only SPOKEN OF as absent (雪球不见了) is not on
            # screen — their plate must not render them into the shot whose
            # whole point is that they are gone
            from app.services.stage_map import (drop_absent_cast,
                                                filter_frame_by_framing)
            _, _abs_notes = drop_absent_cast(
                shots, dialogue_lines=scene.dialogue_json)
            # a framing that cannot physically show a character must not carry
            # them: far-staged cast leave CU/ECU/MCU, INSERTs narrow to their
            # action's participants — otherwise their identity plate rides and
            # the model pastes them in close
            _, _vis_notes = filter_frame_by_framing(
                shots, dialogue_lines=scene.dialogue_json)
            if _abs_notes or _vis_notes:
                import logging
                logging.getLogger(__name__).info(
                    "framing visibility scene %s: %s", scene.number,
                    _abs_notes + _vis_notes)
            # faceless framing normalization runs on the FINAL cast — the
            # reconciliation above can empty a shot's cast (a detail insert of
            # "Anna's hand" whose only listed figure wasn't real cast), and a
            # shot that only NOW became faceless still must not wear a person
            # framing. Running earlier missed exactly those shots.
            if (getattr(get_settings(), "wan_beats", False)
                    or getattr(get_settings(), "ensure_establishing_shot", False)):
                from app.services.storyboard_generator import widen_faceless_framings
                widen_faceless_framings(shots)
            # a sentence staging a NON-cast character makes the model render
            # them anyway ('Theo quickly stands up too' in an Angeline-only
            # MCU produced a second person) — dropped before the Shot persists
            # so the board display and the prompt both read sane
            from app.services.storyboard_generator import (
                face_the_speaker, strip_noncast_action, widen_tight_two_shots)
            for sd in shots:
                sd["action"] = strip_noncast_action(
                    sd.get("action"), sd.get("characters_in_frame"), known_names)
            # a CU/MCU cannot hold two people: a tight two-shot with a known
            # speaker keeps its close intent as an OTS (speaker over the
            # listener's shoulder); otherwise it widens to MS so the render
            # matches the stage diagram instead of dropping a face
            widen_tight_two_shots(shots, dialogue_lines=scene.dialogue_json)
            # LLM-boarded OTS shots sometimes hang the camera behind the
            # SPEAKER — the line goes into the back of a head; re-hang over
            # the listener so the speaker's face carries it
            _fs_notes = face_the_speaker(shots, dialogue_lines=scene.dialogue_json)
            if _fs_notes:
                import logging
                logging.getLogger(__name__).info("face_the_speaker: %s",
                                                 "; ".join(_fs_notes))
            for sd in shots:
                # clamp bounded enum columns (shot_type, camera_movement) so one
                # over-long LLM value can't fail the whole scene's batch insert
                shot = Shot(**clamp_bounded_strings({
                    "scene_id": scene.id, "number": sd.get("shot_number", 1),
                    "shot_type": sd.get("shot_type"), "camera_movement": sd.get("camera_movement"),
                    "lighting": sd.get("lighting"), "colour_mood": sd.get("colour_mood"),
                    "action": sd.get("action"), "dialogue": sd.get("dialogue"),
                    "emotional_beat": sd.get("emotional_beat"),
                    # floor 3s: the video APIs reject shorter requests, and the
                    # Director likes planning 2s beats — those shots hard-failed
                    "estimated_duration_seconds": max(
                        3, int(sd.get("estimated_duration_seconds") or 5)),
                    "characters_in_frame": sd.get("characters_in_frame") or [],
                    "foreground_characters": sd.get("foreground_characters") or [],
                    "blocking_json": ({"subjects": sd.get("subjects"),
                                       "reverse_angle": bool(sd.get("reverse_angle"))}
                                      if sd.get("subjects") else None),
                    "notes": sd.get("notes"),
                    "director_json": sd.get("director_json"),
                }))
                db.add(shot)
                created.append((shot, scene.number))
    tool_event(script.project_id, "storyboard", "shot_breakdown", "succeeded",
               agent="Director", artifact=f"{len(created)} shots")
    tool_event(script.project_id, "storyboard", "set_design", "succeeded",
               agent="Director", artifact=f"{dressed} scenes dressed")
    # recurring-extras check (pure, no I/O): script_generate's rule about naming
    # a recurring unnamed figure is enforced NOWHERE downstream — this catches
    # when it was broken so a shape-shifting extra is flagged, not silently
    # shipped. A WARNING only, like the stage-map corrections above.
    try:
        from app.services.extras_monitor import detect_recurring_extras
        extra_findings = detect_recurring_extras(
            [{"scene_number": scene_no, "shot_number": s.number,
              "action": s.action, "notes": s.notes,
              "characters_in_frame": s.characters_in_frame}
             for s, scene_no in created],
            [c.name for c in characters])
        if extra_findings:
            import logging
            logging.getLogger(__name__).warning(
                "recurring extras in storyboard: %s",
                "; ".join(f["warning"] for f in extra_findings))
            emit("storyboard:extras_warning", {"findings": extra_findings},
                 str(script.project_id))
    except Exception:  # noqa: BLE001 — detection is best-effort, never blocks
        pass
    # continuity check (pure, no I/O): the reliably detectable breaks — a
    # question answered by scenery, a re-staged instant, a frozen emotional
    # beat. The fuzzy continuity rules (state threading, introduce-before-use,
    # arrival beats) are enforced prompt-side; this catches what slipped.
    # A WARNING only, like the extras check above.
    try:
        from app.services.continuity_monitor import detect_continuity_breaks
        by_scene: dict[int, list] = {}
        for s, scene_no in created:
            by_scene.setdefault(scene_no, []).append(s)
        cont_findings = []
        for scene_no, rows in sorted(by_scene.items()):
            rows.sort(key=lambda r: r.number or 0)
            found = detect_continuity_breaks(
                [{"shot_number": r.number, "action": r.action, "dialogue": r.dialogue,
                  "characters_in_frame": r.characters_in_frame,
                  "emotional_beat": r.emotional_beat} for r in rows])
            for f in found:
                f["scene_number"] = scene_no
            cont_findings.extend(found)
        if cont_findings:
            import logging
            logging.getLogger(__name__).warning(
                "continuity breaks in storyboard: %s",
                "; ".join(f"s{f['scene_number']}: {f['warning']}" for f in cont_findings))
            emit("storyboard:continuity_warning", {"findings": cont_findings},
                 str(script.project_id))
    except Exception:  # noqa: BLE001 — detection is best-effort, never blocks
        pass
    # duration fitter: when the board runs past the target, silent beats claim
    # only the time they need (3s) — dialogue keeps what its lines require
    from app.services.storyboard_generator import fit_silent_beats_to_target
    views = [{"estimated_duration_seconds": s.estimated_duration_seconds,
              "dialogue": s.dialogue} for s, _ in created]
    if fit_silent_beats_to_target(views, target_length):
        for (s, _), v in zip(created, views):
            s.estimated_duration_seconds = v["estimated_duration_seconds"]
        _progress(script.project_id, "storyboard", "update", "Director",
                  "Tightened silent beats to fit the target length")
    # over-target check: warn BEFORE render money is spent when the board runs
    # long (the 30s ask that boarded 97s — the script wrote past its budget and
    # every line must still be covered). A WARNING, never a block.
    from app.services.storyboard_generator import board_over_target
    boarded_total = sum(int(s.estimated_duration_seconds or 0) for s, _ in created)
    if board_over_target(boarded_total, target_length):
        import logging
        logging.getLogger(__name__).warning(
            "storyboard runs long: boarded %ss against a %ss target", boarded_total, target_length)
        emit("storyboard:over_target",
             {"boarded_seconds": boarded_total, "target_seconds": target_length},
             str(script.project_id))
        _progress(script.project_id, "storyboard", "update", "Director",
                  f"Heads up: this board plays about {boarded_total}s, over the {target_length}s target")
    with tool_run(script.project_id, "storyboard", "write_shots_db", "Director") as t:
        db.commit()
        t["artifact"] = f"{len(created)} rows"
    # Location plates ride along, exactly like the manual storyboard path:
    # the scenes exist now, so every location gets its background image here
    # instead of waiting for the user to press Generate Plates. Idempotent
    # and an enhancement only — never fails the storyboard.
    try:
        from app.services.casting_director import ensure_location_plates, ensure_style_plate
        _progress(script.project_id, "storyboard", "update", "Director",
                  "Painting location plates")
        with track_project(script.project_id, db):
            await ensure_location_plates(db, script.project_id)
            # the style plate paints HERE too (not at casting): built from the
            # lead's plate so the style frame wears the real cast face
            await ensure_style_plate(db, script.project_id)
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
    # staged under STORYBOARD in the crew graph: the Producer fits the money
    # on the storyboard page (pre-production), not during generation
    with tool_run(project_id, "storyboard", "budget_allocate", "Producer") as t:
        result = TokenOptimizer().allocate(
            shots, budget_usd, wan_primary=getattr(get_settings(), "wan_primary", False))
        tier_by_id = {s["shot_id"]: s["quality_tier"] for s in result["scored_shots"]}
        for sid, tier in tier_by_id.items():
            shot = db.query(Shot).filter(Shot.id == uuid.UUID(sid)).first()
            if shot:
                shot.quality_tier = tier
        db.commit()
        t["artifact"] = f"{len(tier_by_id)} shots fitted"
    from app.agents.reporter import report_agent
    report_agent(db, project_id, agent="budget_allocator", stage="budget",
                 decision={"full": result.get("full_shots"), "fast": result.get("fast_shots")}
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
    """Synthesize dialogue audio (TTS overlay). only_characters restricts the
    run to those speakers' lines (recast after first synthesis) — other
    characters' existing audio is left untouched."""
    from app.services.dialogue_synthesizer import DialogueSynthesizer
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
    # Ride each shot's emotional beat into the line as acting direction —
    # most lines carry no parenthetical, and without direction the instruct
    # TTS reads them flat. COPIES only: the ORM's dialogue_json stays clean.
    scene_dicts = []
    for s in scenes:
        lines = [dict(ln) for ln in (s.dialogue_json or [])]
        try:
            from app.services.dialogue_synthesizer import scene_line_beats
            shot_rows = db.query(Shot).filter(Shot.scene_id == s.id).all()
            beats = scene_line_beats(
                [{"number": sh.number, "dialogue": sh.dialogue,
                  "emotional_beat": sh.emotional_beat} for sh in shot_rows])
            for k, ln in enumerate(lines):
                if k < len(beats) and beats[k] and not ln.get("direction"):
                    ln["direction"] = beats[k]
        except Exception as e:  # noqa: BLE001 — direction is a bonus, never a blocker
            import logging
            logging.getLogger(__name__).warning(
                "beat direction skipped for scene %s: %s", s.number, e)
        scene_dicts.append({"number": s.number, "dialogue_json": lines})
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
