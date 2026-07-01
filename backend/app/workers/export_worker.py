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
from app.config import get_settings

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="run_export")
def run_export(self, project_id: str, job_id: str, clips: list | None = None,
               audio: dict | None = None):
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        job = db.query(GenerationJob).filter(GenerationJob.id == uuid.UUID(job_id)).first()
        if not job:
            return

        trim_by_id: dict = {}
        if clips:
            # Editor supplied an explicit order + per-clip trim — honor it.
            by_id = {
                str(c.id): c
                for c in db.query(GeneratedClip)
                .filter(GeneratedClip.job_id == job.id, GeneratedClip.url.isnot(None))
                .all()
            }
            clips_for_export = []
            for entry in clips:
                cid = str(entry.get("id"))
                if cid in by_id:
                    clips_for_export.append(by_id[cid])
                    trim_by_id[cid] = (entry.get("in"), entry.get("out"))
        else:
            # AI default: every shot that produced a playable clip belongs in
            # the final cut — not just APPROVED. Retries create several rows per
            # shot, so keep the best one per shot (prefer APPROVED, then highest
            # consistency), in shot order.
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
            clips_for_export = list(best_by_shot.values())  # insertion order = shot order

        if not clips_for_export:
            return

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

        # Captions
        srt = caption_gen.generate_srt(clips_with_dialogue)
        srt_path = os.path.join(tempfile.mkdtemp(), "captions.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt)
        srt_key = oss.get_project_path(project_id, "exports", "captions.srt")
        srt_url = oss.upload_file(srt_path, srt_key)

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

        # Download every clip and concatenate into one MP4 with FFmpeg,
        # applying each clip's trim (inpoint/outpoint).
        workdir = tempfile.mkdtemp()
        stitch_inputs = []
        for i, clip in enumerate(clips_for_export):
            local = os.path.join(workdir, f"clip_{i:03d}.mp4")
            try:
                resp = httpx.get(clip.url, timeout=120.0)
                resp.raise_for_status()
                with open(local, "wb") as fh:
                    fh.write(resp.content)
                tin, tout = trim_by_id.get(str(clip.id), (None, None))
                stitch_inputs.append({"path": local, "in": tin, "out": tout})
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Export: could not download clip {clip.id}: {e}")

        if not stitch_inputs:
            logger.error("Export: no clips could be downloaded; aborting")
            return

        stitcher = VideoStitcher()
        final_local = os.path.join(workdir, "final.mp4")
        stitcher.stitch(stitch_inputs, final_local)

        # Optional music track: download and mix over the silent cut.
        if audio and audio.get("url"):
            try:
                ext = audio["url"].rsplit(".", 1)[-1].split("?")[0].lower() or "mp3"
                music_local = os.path.join(workdir, f"music.{ext}")
                a = httpx.get(audio["url"], timeout=120.0)
                a.raise_for_status()
                with open(music_local, "wb") as fh:
                    fh.write(a.content)
                mixed = os.path.join(workdir, "final_audio.mp4")
                stitcher.add_audio(
                    final_local, music_local, mixed,
                    volume=float(audio.get("volume", 1.0)),
                    fade_in=float(audio.get("fade_in", 0.0)),
                    fade_out=float(audio.get("fade_out", 0.0)),
                )
                final_local = mixed
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Export: music mix skipped: {e}")

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
    except Exception as e:  # noqa: BLE001
        logger.error(f"Export failed: {e}")
    finally:
        db.close()
