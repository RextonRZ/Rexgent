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
from app.services.usage_tracker import global_usage
from app.services.audio_timeline import place_dialogue
from app.models.line_audio import LineAudio
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


def _ensure_voice_lines(db, project_id: str) -> None:
    """The manual Generate flow never synthesizes dialogue, so a first export
    would be silent. If no voice lines exist yet, synthesize them now (assigning
    preset voices to any character that skipped casting)."""
    if db.query(LineAudio).filter(LineAudio.project_id == uuid.UUID(project_id)).count():
        return
    try:
        import asyncio
        from app.agent.pipeline_ops import synth_dialogue_op
        asyncio.run(synth_dialogue_op(db, project_id))
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Export: dialogue synth skipped: {e}")


@celery_app.task(bind=True, name="run_export")
def run_export(self, project_id: str, job_id: str, clips: list | None = None,
               audio: dict | None = None):
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        job = db.query(GenerationJob).filter(GenerationJob.id == uuid.UUID(job_id)).first()
        if not job:
            return

        _stage(project_id, "started", "Assembling the final cut")

        by_id = {
            str(c.id): c
            for c in db.query(GeneratedClip)
            .filter(GeneratedClip.job_id == job.id, GeneratedClip.url.isnot(None))
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
            # AI default: best clip per shot, in shot order, untrimmed.
            rows = (
                db.query(GeneratedClip)
                .filter(GeneratedClip.job_id == job.id, GeneratedClip.url.isnot(None))
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
                resolved.append({"url": c.url, "in": None, "out": None, "clip": c})

        if not resolved:
            _stage(project_id, "failed", "Nothing to export yet")
            return

        # Generated-clip subset drives captions + the production report.
        clips_for_export = [r["clip"] for r in resolved if r["clip"]]

        oss = OSSManager(get_settings())
        caption_gen = CaptionGenerator()

        clips_with_dialogue = []
        duration_by_clip = {}
        for clip in clips_for_export:
            shot = db.query(Shot).filter(Shot.id == clip.shot_id).first()
            dur = shot.estimated_duration_seconds if shot else 5
            clips_with_dialogue.append({
                "dialogue": shot.dialogue if shot else None,
                "duration": dur,
            })
            duration_by_clip[str(clip.id)] = dur

        # Production report (token fields populated by Phase 5 token tracking)
        wall_minutes = (
            (datetime.now(timezone.utc) - job.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 60
            if job.created_at else 0.0
        )
        usage = global_usage().snapshot()
        report = build_report(
            project_id=project_id,
            clips=clips_for_export,
            duration_by_clip=duration_by_clip,
            total_retries=sum(c.retries for c in clips_for_export),
            wall_clock_minutes=wall_minutes,
            llm_input_tokens=usage["input_tokens"],
            llm_output_tokens=usage["output_tokens"],
            llm_cost_usd=usage["cost_usd"],
        )
        report_path = os.path.join(tempfile.mkdtemp(), "production_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        report_key = oss.get_project_path(project_id, "exports", "production_report.json")
        oss.upload_file(report_path, report_key)

        # Download every segment and concatenate into one MP4 with FFmpeg,
        # applying each segment's trim (in/out).
        _stage(project_id, "update", f"Fetching {len(resolved)} segment(s)")
        workdir = tempfile.mkdtemp()
        stitch_inputs = []
        for i, seg in enumerate(resolved):
            local = os.path.join(workdir, f"seg_{i:03d}.mp4")
            try:
                resp = httpx.get(seg["url"], timeout=180.0)
                resp.raise_for_status()
                with open(local, "wb") as fh:
                    fh.write(resp.content)
                stitch_inputs.append({"path": local, "in": seg["in"], "out": seg["out"]})
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
        final_local = os.path.join(workdir, "final.mp4")
        _stage(project_id, "update", f"Stitching {len(stitch_inputs)} clip(s)")
        stitcher.stitch(stitch_inputs, final_local, ratio=ratio)

        # ── Dialogue placement: each line aligned to the shot that speaks it ──
        dialogue_segments: list = []
        bgm_local = None
        try:
            from app.models.script import Script, Scene

            # Make sure voice lines exist before we try to place them.
            _ensure_voice_lines(db, project_id)

            script = (db.query(Script).filter(Script.project_id == uuid.UUID(project_id))
                      .order_by(Script.created_at.desc()).first())
            # Per-scene shot layout (duration + which shots carry dialogue) so voice
            # lines land on the matching picture.
            scene_plan = []
            if script:
                scenes = db.query(Scene).filter(Scene.script_id == script.id).order_by(Scene.number).all()
                for s in scenes:
                    sh = db.query(Shot).filter(Shot.scene_id == s.id).order_by(Shot.number).all()
                    scene_plan.append({
                        "scene_number": s.number,
                        "shots": [
                            {"duration": x.estimated_duration_seconds or 5,
                             "has_dialogue": bool((x.dialogue or "").strip())}
                            for x in sh
                        ],
                    })
            line_rows = []
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
            dialogue_segments = build_dialogue_segments(line_rows, scene_plan)

            if audio and audio.get("url"):
                ext = audio["url"].rsplit(".", 1)[-1].split("?")[0].lower() or "mp3"
                bgm_local = os.path.join(workdir, f"music.{ext}")
                a = httpx.get(audio["url"], timeout=120.0)
                a.raise_for_status()
                with open(bgm_local, "wb") as fh:
                    fh.write(a.content)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Export: audio prep skipped: {e}")

        # ── Captions: timed to the placed voice lines when they exist, else to
        # shot durations. Burned into the picture (short dramas are watched
        # muted-first) AND uploaded as a sidecar .srt.
        srt_url = None
        try:
            spoken = [s for s in dialogue_segments if s.get("text")]
            srt = (caption_gen.generate_srt_from_segments(spoken) if spoken
                   else caption_gen.generate_srt(clips_with_dialogue))
            if srt.strip():
                srt_path = os.path.join(workdir, "captions.srt")
                with open(srt_path, "w", encoding="utf-8") as f:
                    f.write(srt)
                srt_key = oss.get_project_path(project_id, "exports", "captions.srt")
                srt_url = oss.upload_file(srt_path, srt_key)
                burned = os.path.join(workdir, "final_subbed.mp4")
                _stage(project_id, "update", "Burning captions into the picture")
                stitcher.burn_subtitles(final_local, srt_path, burned)
                final_local = burned
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Export: subtitle burn skipped: {e}")

        # ── Mix: dialogue track + optional BGM bed ducking under speech ──
        try:
            from app.websocket.emitter import emit
            if dialogue_segments or bgm_local:
                emit("audio.mix.started", {}, project_id)
                mixed = os.path.join(workdir, "final_audio.mp4")
                stitcher.mix_tracks(
                    final_local, dialogue_segments, bgm_local, mixed,
                    bgm_volume=float(audio.get("volume", 0.3)) if audio else 0.3,
                    duck=bool(audio.get("duck", True)) if audio else True,
                )
                final_local = mixed
                emit("audio.mix.completed", {}, project_id)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Export: audio mix skipped: {e}")

        _stage(project_id, "update", "Uploading the final cut")
        final_key = oss.get_project_path(project_id, "exports", "final.mp4")
        final_url = oss.upload_file(final_local, final_key)

        export = FinalExport(
            project_id=uuid.UUID(project_id),
            url=final_url,
            duration_seconds=report["total_duration_seconds"],
            caption_url=srt_url,
            report_json=report,
        )
        db.add(export)
        db.commit()
        try:
            from app.websocket.emitter import emit
            emit("export.completed", {"url": final_url,
                 "duration": report["total_duration_seconds"]}, project_id)
        except Exception:  # noqa: BLE001
            pass
        _stage(project_id, "completed", "Final cut ready")
    except Exception as e:  # noqa: BLE001
        logger.error(f"Export failed: {e}")
        _stage(project_id, "failed", "Export failed")
    finally:
        db.close()
