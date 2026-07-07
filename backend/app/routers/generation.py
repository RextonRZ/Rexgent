import re
import time
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.project import Project
from app.models.generation_job import GenerationJob
from app.models.generated_clip import GeneratedClip
from app.models.shot import Shot
from app.schemas.generation import GenerationStartRequest, GenerationJobStatus, ClipResult
from app.services.cost_rates import video_cost
from app.workers.generation_worker import run_generation_job

router = APIRouter(prefix="/api/generate", tags=["generation"])


@router.post("/start", response_model=GenerationJobStatus)
async def start_generation(request: GenerationStartRequest, db: Session = Depends(get_db)):
    if not db.query(Project).filter(Project.id == request.project_id).first():
        raise HTTPException(status_code=404, detail="Project not found")

    job = GenerationJob(project_id=request.project_id)
    db.add(job)
    db.commit()
    db.refresh(job)
    # light the pipeline the instant the user clicks — the celery worker may
    # take seconds to pick the job up, and its own first event even longer
    from app.websocket.emitter import emit
    emit("stage:progress", {"stage": "generate", "status": "started",
         "agent": "Showrunner", "label": "Dispatching the render crew"},
         str(request.project_id))
    run_generation_job.delay(str(job.id))
    return job


@router.get("/{job_id}/status", response_model=GenerationJobStatus)
async def get_job_status(job_id: str, db: Session = Depends(get_db)):
    job = db.query(GenerationJob).filter(GenerationJob.id == uuid.UUID(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/clips")
async def get_job_clips(job_id: str, db: Session = Depends(get_db)):
    clips = db.query(GeneratedClip).filter(GeneratedClip.job_id == uuid.UUID(job_id)).all()

    shot_ids = {c.shot_id for c in clips}
    shots = db.query(Shot).filter(Shot.id.in_(shot_ids)).all() if shot_ids else []
    duration_by_shot = {s.id: (s.estimated_duration_seconds or 5) for s in shots}

    results = []
    for c in clips:
        item = ClipResult.model_validate(c)
        duration = duration_by_shot.get(c.shot_id, 5)
        item.cost_usd = video_cost(duration, c.model_used)
        results.append(item)
    return {"clips": results}


def _url_expired(url: str | None) -> bool:
    """Old clips stored DashScope's signed URLs, which die after ~24h. Their
    Expires=<unix ts> query param tells us which are already dead — hide those
    instead of rendering broken players. (Our OSS re-hosted clips never match.)"""
    m = re.search(r"[?&]Expires=(\d+)", url or "")
    return bool(m) and int(m.group(1)) < time.time()


@router.get("/project/{project_id}/clips")
async def project_clips(project_id: str, db: Session = Depends(get_db)):
    """All playable clips for a project across ALL jobs. The per-job route breaks
    when the newest job is an empty duplicate or when a storyboard regeneration
    replaced the shots — this keeps every generated video reachable."""
    pid = uuid.UUID(project_id)
    job_ids = [j.id for j in db.query(GenerationJob).filter(GenerationJob.project_id == pid).all()]
    if not job_ids:
        return {"clips": []}
    clips = (db.query(GeneratedClip)
             .filter(GeneratedClip.job_id.in_(job_ids), GeneratedClip.url.isnot(None))
             .order_by(GeneratedClip.created_at.desc())
             .all())
    clips = [c for c in clips if not _url_expired(c.url)]

    shot_ids = {c.shot_id for c in clips if c.shot_id}
    shots = db.query(Shot).filter(Shot.id.in_(shot_ids)).all() if shot_ids else []
    duration_by_shot = {s.id: (s.estimated_duration_seconds or 5) for s in shots}

    results = []
    for c in clips:
        item = ClipResult.model_validate(c)
        item.cost_usd = video_cost(duration_by_shot.get(c.shot_id, 5), c.model_used)
        results.append(item)
    return {"clips": results}


@router.get("/project/{project_id}/latest", response_model=GenerationJobStatus)
async def latest_job(project_id: str, db: Session = Depends(get_db)):
    job = (
        db.query(GenerationJob)
        .filter(GenerationJob.project_id == uuid.UUID(project_id))
        .order_by(GenerationJob.created_at.desc())
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="No job for project")
    return job
