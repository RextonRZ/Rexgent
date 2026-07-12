import uuid
import json
import tempfile
import os
import logging
import httpx
from datetime import datetime, timezone
from app.workers.celery_app import celery_app
from app.services.video_stitcher import VideoStitcher
from app.database import get_session_factory
from app.models.generation_job import GenerationJob
from app.models.generated_clip import GeneratedClip
from app.models.shot import Shot
from app.models.final_export import FinalExport
from app.services.caption_generator import CaptionGenerator
from app.services.production_report import build_report
from app.services.oss_manager import OSSManager
from app.services.audio_timeline import place_dialogue
from app.models.line_audio import LineAudio
from app.websocket.tool_events import tool_event, tool_run
from app.config import get_settings

logger = logging.getLogger(__name__)


def _stage(project_id: str, status: str, label: str) -> None:
    """Export progress on the shared stage:progress channel — the same pipe the
    agent chat, crew modal and pipeline nav already listen to. Never fatal."""
    try:
        from app.websocket.emitter import emit
        emit("stage:progress", {"stage": "export", "status": status,
             "agent": "Editor", "label": label}, project_id)
    except Exception:  # noqa: BLE001
        pass


def build_dialogue_segments(line_rows, scene_plan):
    """Place per-line dialogue audio on the global timeline, aligning each line to
    the shot that speaks it. line_rows: dicts with scene_number, line_index,
    audio_local, duration_seconds (+ optional text/character_name, which ride
    along so burned captions share the voice's exact timing). scene_plan:
    ordered per-scene shot layout."""
    rows = [
        {"scene_number": r["scene_number"], "line_index": r["line_index"],
         "audio_path": r["audio_local"], "duration": r["duration_seconds"],
         "text": r.get("text"), "character": r.get("character_name")}
        for r in line_rows
    ]
    return place_dialogue(rows, scene_plan)


def build_cut_plan(entries: list[dict]) -> list[dict]:
    """Fold the ACTUAL export cut — ordered chunks with real (probed)
    durations — into the scene_plan shape place_dialogue consumes.
    entries: [{scene_number|None, duration, has_dialogue}] in cut order.
    Consecutive same-scene chunks merge into one group; imported media
    (scene_number None) rides along as silent screen time. Building the
    timeline from the cut instead of the storyboard is what keeps voices on
    their pictures when a shot was deferred, failed, trimmed, or footage was
    imported."""
    plan: list[dict] = []
    for e in entries:
        shot = {"duration": float(e.get("duration") or 0.0),
                "has_dialogue": bool(e.get("has_dialogue")),
                "speech_onset": e.get("speech_onset"),
                "mouth_dur": e.get("mouth_dur")}
        if plan and plan[-1]["scene_number"] == e.get("scene_number"):
            plan[-1]["shots"].append(shot)
        else:
            plan.append({"scene_number": e.get("scene_number"), "shots": [shot]})
    return plan


def characters_needing_resynthesis(rows, current_voice_by_name, script_speakers,
                                   script_line_keys=None) -> set:
    """Names whose dialogue audio no longer matches casting: their lines were
    synthesized with a different voice_id than the character's CURRENT one
    (recast after generation; rows with NO recorded voice count too), or they
    speak in the script but audio is missing — either no lines at all, or
    individual line slots that a flaky TTS call skipped (script_line_keys:
    {(scene_number, line_index, character)}). Pure function so the recast
    rules are testable."""
    from app.services.guardrails import canonical_character
    stale = set()
    for r in rows:
        # "CATHERINE (V.O.)" rows are judged against CATHERINE's current
        # voice — a stage qualifier must not exempt a line from recasting
        cur = (current_voice_by_name.get(r.character_name)
               or current_voice_by_name.get(
                   canonical_character(r.character_name or "", current_voice_by_name)))
        if cur and r.voice_id != cur:
            stale.add(r.character_name)
    have = {r.character_name for r in rows}
    missing = {s for s in script_speakers if s not in have}
    if script_line_keys:
        have_slots = {(r.scene_number, r.line_index) for r in rows}
        missing |= {ch for (sc, li, ch) in script_line_keys
                    if ch in script_speakers and (sc, li) not in have_slots}
    return stale | missing


def _ensure_voice_lines(db, project_id: str) -> None:
    """Make the dialogue audio match casting before the mix.
    - No lines at all (manual Generate never synthesizes) -> synthesize everything.
    - A character was recast (voice_id on their lines != their current voice,
      e.g. switched preset or enrolled a clone) -> re-synthesize ONLY their lines.
    Other characters' audio is reused, so a recast costs TTS for one character,
    not the whole script."""
    try:
        import asyncio
        from app.models.character import Character
        from app.models.script import Script, Scene
        from app.agent.pipeline_ops import synth_dialogue_op

        pid = uuid.UUID(project_id)
        rows = db.query(LineAudio).filter(LineAudio.project_id == pid).all()
        if not rows:
            asyncio.run(synth_dialogue_op(db, project_id))
            return

        chars = db.query(Character).filter(Character.project_id == pid).all()
        current = {c.name: c.voice_id for c in chars if c.voice_id}
        speakers: set = set()
        line_keys: set = set()
        script = (db.query(Script).filter(Script.project_id == pid)
                  .order_by(Script.created_at.desc()).first())
        if script:
            for s in db.query(Scene).filter(Scene.script_id == script.id).all():
                for li, line in enumerate(s.dialogue_json or []):
                    if line.get("character"):
                        speakers.add(line["character"])
                        line_keys.add((s.number, li, line["character"]))

        redo = characters_needing_resynthesis(rows, current, speakers, line_keys)
        if redo:
            logger.info(f"Export: re-synthesizing recast voices for {sorted(redo)}")
            asyncio.run(synth_dialogue_op(db, project_id, only_characters=redo))
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Export: dialogue synth skipped: {e}")


def _retime_rushed_lines(db, project_id: str, line_rows: list, scene_plan: list,
                         workdir: str) -> None:
    """Pacing retakes: a designed voice can speak a short line far faster than
    the rendered mouth moves, and atempo may only slow it ~25% before it
    slurs. Any line still shorter than its mouth at the clamp is RE-PERFORMED
    with written pauses (ellipses at phrase boundaries), escalating one pause
    at a time until the take fits — a slower performance instead of a
    stretched one. Captions keep the original text; the retimed audio and
    duration persist to LineAudio so preview and every later export agree."""
    from app.services.audio_timeline import pacing_retakes, paced_text, TEMPO_MIN
    targets = pacing_retakes(line_rows, scene_plan)
    if not targets:
        return
    import asyncio
    from app.config import get_settings
    from app.models.character import Character
    from app.services.dialogue_synthesizer import probe_duration
    from app.services.guardrails import canonical_character
    from app.services.oss_manager import OSSManager
    from app.services.qwen_client import QwenClient
    settings = get_settings()
    qwen, oss = QwenClient(settings), OSSManager(settings)
    chars = db.query(Character).filter(Character.project_id == uuid.UUID(project_id)).all()
    by_name = {c.name: c for c in chars if c.voice_id}
    for ln, mouth in targets:
        raw_name = ln.get("character_name") or ""
        c = by_name.get(raw_name) or by_name.get(canonical_character(raw_name, by_name))
        if not c:
            continue
        best = None  # (duration, audio_bytes, level)
        for level in (1, 2, 3, 4):
            text = paced_text(ln.get("text") or "", level)
            try:
                audio = asyncio.run(qwen.synthesize_speech(text, c.voice_id, c.voice_model))
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Export: pacing retake synth failed: {e}")
                break
            dur = probe_duration(audio)
            if best is None or dur > best[0]:
                best = (dur, audio, level)
            if mouth and dur / mouth >= TEMPO_MIN:
                break
        # only adopt a retake that actually got closer to the mouth
        if not best or best[0] <= float(ln.get("duration_seconds") or 0.0):
            continue
        dur, audio, level = best
        key = oss.get_project_path(project_id, "audio",
                                   f"s{ln['scene_number']}_l{ln['line_index']}_paced.wav")
        url = oss.upload_bytes(audio, key, content_type="audio/wav")
        row = (db.query(LineAudio)
               .filter(LineAudio.project_id == uuid.UUID(project_id),
                       LineAudio.scene_number == ln["scene_number"],
                       LineAudio.line_index == ln["line_index"]).first())
        if row is not None:
            row.audio_url, row.duration_seconds = url, dur
            db.commit()
        lp = os.path.join(workdir, f"line_{ln['scene_number']}_{ln['line_index']}_paced.wav")
        with open(lp, "wb") as fh:
            fh.write(audio)
        ln["audio_local"], ln["duration_seconds"] = lp, dur
        logger.info(
            f"Export: pacing retake s{ln['scene_number']}l{ln['line_index']} "
            f"({level} pause(s)): {dur:.2f}s toward mouth {mouth:.2f}s")


def assign_episodes(cut_entries: list, episode_by_scene: dict) -> list[int]:
    """Which episode each cut chunk belongs to. Scene-less chunks (imported
    media) ride the episode currently playing; anything unknown is episode 1,
    so a single-episode drama always resolves to one deliverable."""
    out: list[int] = []
    last: int | None = None
    for e in cut_entries:
        scene = e.get("scene_number")
        ep = episode_by_scene.get(scene) if scene is not None else None
        if ep is None:
            ep = last or 1
        out.append(int(ep))
        last = int(ep)
    return out


@celery_app.task(bind=True, name="run_export")
def run_export(self, project_id: str, job_id: str, clips: list | None = None,
               audio: dict | None = None):
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        from app.services.api_keys import use_project_key
        use_project_key(db, project_id)  # bill the project owner's key
        job = db.query(GenerationJob).filter(GenerationJob.id == uuid.UUID(job_id)).first()
        if not job:
            return

        _stage(project_id, "started", "Assembling the final cut")

        # Clips across ALL of the project's jobs: a resume run re-renders only
        # the rejected shots, so scoping to job.id would export a 3-shot cut
        # of a 12-shot drama (the auto-export did exactly that in production)
        project_job_ids = [
            j.id for j in db.query(GenerationJob)
            .filter(GenerationJob.project_id == job.project_id).all()
        ]
        by_id = {
            str(c.id): c
            for c in db.query(GeneratedClip)
            .filter(GeneratedClip.job_id.in_(project_job_ids),
                    GeneratedClip.url.isnot(None))
            .all()
        }
        # Ordered segments to stitch: each is {url, in, out, clip?}. A segment is
        # either a generated clip (clip set) or an imported media URL (clip None).
        resolved: list = []
        if clips:
            for entry in clips:
                url = entry.get("url")
                cid = entry.get("id")
                if url:
                    resolved.append({"url": url, "in": entry.get("in"), "out": entry.get("out"), "clip": None})
                elif cid and str(cid) in by_id:
                    c = by_id[str(cid)]
                    resolved.append({"url": c.url, "in": entry.get("in"), "out": entry.get("out"), "clip": c})
        else:
            # AI default: best clip per shot across every job, in shot order.
            rows = (
                db.query(GeneratedClip)
                .filter(GeneratedClip.job_id.in_(project_job_ids),
                        GeneratedClip.url.isnot(None))
                .join(Shot, GeneratedClip.shot_id == Shot.id)
                .order_by(Shot.number)
                .all()
            )
            best_by_shot: dict = {}
            for clip in rows:
                key = clip.shot_id
                current = best_by_shot.get(key)
                rank = (clip.status == "APPROVED", clip.consistency_score or 0.0)
                if current is None or rank > (current.status == "APPROVED", current.consistency_score or 0.0):
                    best_by_shot[key] = clip
            for c in best_by_shot.values():
                # editor trims persist on the clip — the AI default honors them
                resolved.append({"url": c.url,
                                 "in": getattr(c, "trim_start", None),
                                 "out": getattr(c, "trim_end", None),
                                 "clip": c})

        if not resolved:
            _stage(project_id, "failed", "Nothing to export yet")
            return

        # Generated-clip subset drives captions + the production report.
        clips_for_export = [r["clip"] for r in resolved if r["clip"]]

        oss = OSSManager(get_settings())
        caption_gen = CaptionGenerator()

        duration_by_clip = {}
        for clip in clips_for_export:
            shot = db.query(Shot).filter(Shot.id == clip.shot_id).first()
            duration_by_clip[str(clip.id)] = (
                shot.estimated_duration_seconds if shot else 5)

        # Production report (token fields populated by Phase 5 token tracking)
        wall_minutes = (
            (datetime.now(timezone.utc) - job.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 60
            if job.created_at else 0.0
        )
        # LLM figures come from the LEDGER — the worker's in-process tracker is
        # empty here (every real call lands on cost_events via track_project),
        # and the report is the artifact that proves the budget held.
        from app.services.cost_ledger import aggregate
        ledger = aggregate(db, project_id)
        by_cat = ledger.get("by_category", {})
        report = build_report(
            project_id=project_id,
            clips=clips_for_export,
            duration_by_clip=duration_by_clip,
            total_retries=sum(c.retries for c in clips_for_export),
            wall_clock_minutes=wall_minutes,
            llm_input_tokens=ledger["llm"]["input_tokens"],
            llm_output_tokens=ledger["llm"]["output_tokens"],
            llm_cost_usd=by_cat.get("llm", 0.0),
            other_costs_usd=by_cat.get("image", 0.0) + by_cat.get("tts", 0.0),
            budget=ledger.get("budget", 40.0),
        )
        report_path = os.path.join(tempfile.mkdtemp(), "production_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        report_key = oss.get_project_path(project_id, "exports", "production_report.json")
        oss.upload_file(report_path, report_key)

        # Download every segment and concatenate into one MP4 with FFmpeg,
        # applying each segment's trim (in/out). A dialogue shot's ORIGINAL
        # audio is muted — the model fakes its own speech on those, which
        # would murmur under the real TTS voices; scenery shots keep their
        # ambience. Imported media is never muted.
        from app.models.script import Scene
        shot_meta: dict = {}
        if clips_for_export:
            for s, scene_no in (db.query(Shot, Scene.number)
                                .join(Scene, Shot.scene_id == Scene.id)
                                .filter(Shot.id.in_([c.shot_id for c in clips_for_export]))
                                .all()):
                shot_meta[str(s.id)] = {"scene": scene_no,
                                        "dialogue": (s.dialogue or "").strip()}
        _stage(project_id, "update", f"Fetching {len(resolved)} segment(s)")
        workdir = tempfile.mkdtemp()
        stitch_inputs = []
        # the ACTUAL cut, chunk by chunk, with REAL durations — dialogue and
        # captions are placed on this, not on the storyboard's estimates
        cut_entries: list = []
        kept_beds = 0
        for i, seg in enumerate(resolved):
            local = os.path.join(workdir, f"seg_{i:03d}.mp4")
            meta = shot_meta.get(str(seg["clip"].shot_id)) if seg["clip"] else None
            has_dialogue = bool(meta and meta["dialogue"])
            try:
                resp = httpx.get(seg["url"], timeout=180.0)
                resp.raise_for_status()
                with open(local, "wb") as fh:
                    fh.write(resp.content)
                # the model's own music/ambience/SFX survive whenever the
                # track carries no real words — the clip's STORED verdict wins
                # (the preview showed the same one); compute only when missing
                policy = getattr(seg["clip"], "audio_json", None) if seg["clip"] else None
                if isinstance(policy, dict) and "mute" in policy:
                    mute, vol = bool(policy.get("mute")), policy.get("volume")
                else:
                    from app.services.audio_policy import bed_decision
                    mute, vol = bed_decision(local, has_dialogue)
                    if seg["clip"] is not None:
                        try:
                            seg["clip"].audio_json = {"mute": mute, "volume": vol}
                            db.commit()
                        except Exception:  # noqa: BLE001
                            db.rollback()
                if vol is not None:
                    kept_beds += 1
                    logger.info("chunk %d: original soundtrack kept as bed", i)
                # what this chunk really contributes to the final timeline
                probed = VideoStitcher._duration(local)
                tin = float(seg["in"] or 0.0)
                if seg["out"] is not None:
                    eff = float(seg["out"]) - tin
                    if probed > 0:
                        eff = min(eff, max(0.0, probed - tin))
                elif probed > 0:
                    eff = max(0.0, probed - tin)
                else:  # probe failed — fall back to the storyboard estimate
                    eff = duration_by_clip.get(str(seg["clip"].id), 5) if seg["clip"] else 5
                onset, mouth = None, None
                if meta and meta["dialogue"] and isinstance(policy, dict):
                    raw_onset = policy.get("onset")
                    if raw_onset is not None:
                        onset = min(max(0.0, float(raw_onset) - tin),
                                    max(0.0, eff - 1.0))
                        raw_mouth = policy.get("mouth_dur")
                        if raw_mouth:
                            # the mouth can't talk past the chunk's end
                            mouth = min(float(raw_mouth), max(0.0, eff - onset))
                cut_entries.append({
                    "scene_number": meta["scene"] if meta else None,
                    "duration": eff,
                    "has_dialogue": bool(meta and meta["dialogue"]),
                    "text": meta["dialogue"] if meta else None,
                    "speech_onset": onset,
                    "mouth_dur": mouth,
                })
                # appended LAST so stitch_inputs and cut_entries always align
                # index-for-index (episode slicing depends on it)
                stitch_inputs.append({"path": local, "in": seg["in"], "out": seg["out"],
                                      "mute": mute, "volume": vol})
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Export: could not download {seg['url']}: {e}")

        if not stitch_inputs:
            logger.error("Export: no segments could be downloaded; aborting")
            _stage(project_id, "failed", "Could not download any footage")
            return

        # The drama's delivery format (chosen at creation) sets the canvas.
        from app.models.project import Project
        project = db.query(Project).filter(Project.id == uuid.UUID(project_id)).first()
        ratio = (getattr(project, "video_ratio", None) or "9:16")
        stitcher = VideoStitcher()
        if kept_beds:
            _stage(project_id, "update",
                   f"Keeping {kept_beds} original soundtrack(s) as the ambient bed")

        # ── User-chosen music: downloaded on its OWN so a dialogue-prep hiccup
        # can never silently drop the track the user set ──
        bgm_local = None
        if audio and audio.get("url"):
            try:
                ext = audio["url"].rsplit(".", 1)[-1].split("?")[0].lower() or "mp3"
                bgm_local = os.path.join(workdir, f"music.{ext}")
                a = httpx.get(audio["url"], timeout=120.0)
                a.raise_for_status()
                with open(bgm_local, "wb") as fh:
                    fh.write(a.content)
            except Exception as e:  # noqa: BLE001
                bgm_local = None
                logger.warning(f"Export: music download failed: {e}")

        # ── Voice lines: ensured and downloaded ONCE; every cut places from
        # the same pool (placement is scene-keyed, so a line can only land in
        # the cut that contains its scene) ──
        line_rows: list = []
        try:
            tool_event(project_id, "export", "synth_voices", "started", agent="Audio Mixer")
            _ensure_voice_lines(db, project_id)
            tool_event(project_id, "export", "synth_voices", "succeeded", agent="Audio Mixer",
                       artifact="voices match casting")
            for row in db.query(LineAudio).filter(LineAudio.project_id == uuid.UUID(project_id)).all():
                if not row.audio_url:
                    continue
                lp = os.path.join(workdir, f"line_{row.scene_number}_{row.line_index}.wav")
                try:
                    lr = httpx.get(row.audio_url, timeout=120.0)
                    lr.raise_for_status()
                    with open(lp, "wb") as fh:
                        fh.write(lr.content)
                    line_rows.append({"scene_number": row.scene_number, "line_index": row.line_index,
                                      "audio_local": lp, "duration_seconds": row.duration_seconds or 0.0,
                                      "text": row.text, "character_name": row.character_name})
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"Export: could not download line audio {row.audio_url}: {e}")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Export: voice prep skipped: {e}")

        def _render_cut(suffix: str, inputs: list, entries: list, label: str) -> dict:
            """Stitch, place dialogue, burn captions, mix, upload ONE
            deliverable. An empty suffix keeps the legacy single-video keys so
            a one-episode drama exports byte-identically to before."""
            cut_local = os.path.join(workdir, f"final{suffix}.mp4")
            _stage(project_id, "update", f"Stitching {len(inputs)} clip(s){label}")
            with tool_run(project_id, "export", "stitch_clips", "Editor") as t:
                stitcher.stitch(inputs, cut_local, ratio=ratio)
                t["artifact"] = f"{len(inputs)} clips{label}"

            # ── Dialogue placement: each line aligned to the shot that speaks
            # it, on THIS cut's real probed chunk durations ──
            dialogue_segments: list = []
            try:
                scene_plan = build_cut_plan(entries)
                # a line the clamp can't slow enough gets a paused re-performance
                try:
                    _retime_rushed_lines(db, project_id, line_rows, scene_plan, workdir)
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"Export: pacing retakes skipped{label}: {e}")
                with tool_run(project_id, "export", "assemble_timeline", "Editor") as t:
                    dialogue_segments = build_dialogue_segments(line_rows, scene_plan)
                    t["artifact"] = f"{len(dialogue_segments)} lines placed{label}"
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Export: dialogue prep skipped{label}: {e}")

            # ── A held ending: when the final voice line outruns the footage,
            # freeze the last frame long enough for it to finish (plus a beat)
            # instead of cutting the speech off with the video ──
            try:
                vid_dur = VideoStitcher._duration(cut_local)
                speech_end = max(
                    (float(s["start"]) + float(s.get("duration") or 0.0)
                     for s in dialogue_segments), default=0.0)
                pad = max(0.0, speech_end + 0.4 - vid_dur) if vid_dur > 0 else 0.0
                if pad > 0.05:
                    padded = os.path.join(workdir, f"final_padded{suffix}.mp4")
                    stitcher.pad_tail(cut_local, padded, pad)
                    cut_local = padded
                    logger.info("ending held %.2fs for the last line%s", pad, label)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Export: ending hold skipped{label}: {e}")

            # ── Captions: timed to the placed voice lines when they exist,
            # else to chunk durations. Burned in AND uploaded as sidecar .srt ──
            srt_url = None
            try:
                spoken = [s for s in dialogue_segments if s.get("text")]
                cut_captions = [{"dialogue": e.get("text"), "duration": e["duration"]}
                                for e in entries]
                srt = (caption_gen.generate_srt_from_segments(spoken) if spoken
                       else caption_gen.generate_srt(cut_captions))
                if srt.strip():
                    srt_path = os.path.join(workdir, f"captions{suffix}.srt")
                    with open(srt_path, "w", encoding="utf-8") as f:
                        f.write(srt)
                    srt_key = oss.get_project_path(project_id, "exports", f"captions{suffix}.srt")
                    srt_url = oss.upload_file(srt_path, srt_key)
                    burned = os.path.join(workdir, f"final_subbed{suffix}.mp4")
                    _stage(project_id, "update", f"Burning captions into the picture{label}")
                    with tool_run(project_id, "export", "burn_captions", "Editor") as t:
                        stitcher.burn_subtitles(cut_local, srt_path, burned)
                        t["artifact"] = f"captions burned + .srt{label}"
                    cut_local = burned
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Export: subtitle burn skipped{label}: {e}")

            # ── Mix: dialogue track + optional BGM bed ducking under speech ──
            try:
                from app.websocket.emitter import emit
                if dialogue_segments or bgm_local:
                    emit("audio.mix.started", {}, project_id)
                    mixed = os.path.join(workdir, f"final_audio{suffix}.mp4")
                    with tool_run(project_id, "export", "mix_audio", "Audio Mixer") as t:
                        stitcher.mix_tracks(
                            cut_local, dialogue_segments, bgm_local, mixed,
                            bgm_volume=float(audio.get("volume", 1.0)) if audio else 1.0,
                            duck=bool(audio.get("duck", True)) if audio else True,
                            bgm_fade_in=float(audio.get("fade_in", 0.0)) if audio else 0.0,
                            bgm_fade_out=float(audio.get("fade_out", 0.0)) if audio else 0.0,
                        )
                        t["artifact"] = (f"{len(dialogue_segments)} voices"
                                         + (" + music" if bgm_local else ""))
                    cut_local = mixed
                    emit("audio.mix.completed", {}, project_id)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Export: audio mix skipped{label}: {e}")

            # ── The ending fade: picture and sound land together instead of
            # stopping mid-frame ──
            try:
                faded = os.path.join(workdir, f"final_faded{suffix}.mp4")
                stitcher.fade_tail(cut_local, faded)
                cut_local = faded
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Export: ending fade skipped{label}: {e}")

            _stage(project_id, "update", f"Uploading the final cut{label}")
            with tool_run(project_id, "export", "render_mp4", "Editor") as t:
                final_key = oss.get_project_path(project_id, "exports", f"final{suffix}.mp4")
                url = oss.upload_file(cut_local, final_key)
                t["artifact"] = f"1 mp4{label}"
            return {"url": url, "caption_url": srt_url,
                    "duration_seconds": round(sum(e["duration"] for e in entries), 2)}

        # ── Episode boundaries: the structurer records each scene's episode.
        # One episode keeps the legacy final.mp4; N episodes deliver N videos ──
        episode_by_scene: dict = {}
        try:
            from app.models.script import Script
            script = (db.query(Script).filter(Script.project_id == uuid.UUID(project_id))
                      .order_by(Script.created_at.desc()).first())
            for sc in (((script.structured_json or {}).get("scenes") or []) if script else []):
                if sc.get("scene_number") is not None:
                    episode_by_scene[int(sc["scene_number"])] = int(sc.get("episode_number") or 1)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Export: episode mapping unavailable: {e}")
        chunk_eps = assign_episodes(cut_entries, episode_by_scene)
        episode_numbers = sorted(set(chunk_eps))

        deliverables: list = []
        if episode_numbers in ([], [1]):
            # the legacy single-video path, byte-identical keys
            deliverables.append({"episode": 1,
                                 **_render_cut("", stitch_inputs, cut_entries, "")})
        else:
            # every other shape gets per-episode keys — including an export of
            # ONLY episode 2, which must not overwrite the combined final.mp4
            for ep in episode_numbers:
                idxs = [i for i, ce in enumerate(chunk_eps) if ce == ep]
                deliverables.append({"episode": ep,
                                     **_render_cut(f"_ep{ep}",
                                                   [stitch_inputs[i] for i in idxs],
                                                   [cut_entries[i] for i in idxs],
                                                   f" (episode {ep})")})
            report["episodes"] = deliverables

        primary = deliverables[0]
        with tool_run(project_id, "export", "write_export_db", "Editor") as t:
            export = FinalExport(
                project_id=uuid.UUID(project_id),
                url=primary["url"],
                duration_seconds=report["total_duration_seconds"],
                caption_url=primary["caption_url"],
                report_json=report,
            )
            db.add(export)
            db.commit()
            t["artifact"] = f"{len(deliverables)} export deliverable(s)"
        try:
            from app.websocket.emitter import emit
            emit("export.completed", {"url": primary["url"],
                 "duration": report["total_duration_seconds"]}, project_id)
        except Exception:  # noqa: BLE001
            pass
        _stage(project_id, "completed",
               "Final cut ready" if len(deliverables) == 1
               else f"{len(deliverables)} episode cuts ready")
    except Exception as e:  # noqa: BLE001
        logger.error(f"Export failed: {e}")
        _stage(project_id, "failed", "Export failed")
    finally:
        db.close()
