import uuid
import json
import tempfile
import os
import logging
from datetime import datetime, timezone
from app.workers.celery_app import celery_app
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
def run_export(self, project_id: str, job_id: str):
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        job = db.query(GenerationJob).filter(GenerationJob.id == uuid.UUID(job_id)).first()
        if not job:
            return

        approved = (
            db.query(GeneratedClip)
            .filter(GeneratedClip.job_id == job.id, GeneratedClip.status == "APPROVED")
            .join(Shot, GeneratedClip.shot_id == Shot.id)
            .order_by(Shot.number)
            .all()
        )
        if not approved:
            return

        oss = OSSManager(get_settings())
        caption_gen = CaptionGenerator()

        clips_with_dialogue = []
        duration_by_clip = {}
        for clip in approved:
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
            clips=approved,
            duration_by_clip=duration_by_clip,
            total_retries=sum(c.retries for c in approved),
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

        # For the hackathon, the final stitched video uses the approved clip URLs.
        # (Full FFmpeg concat runs when clips are downloaded locally.)
        final_url = approved[0].url

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
