import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.project import Project
from app.models.generation_job import GenerationJob
from app.models.generated_clip import GeneratedClip
from app.schemas.generation import GenerationStartRequest, GenerationJobStatus, ClipResult
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
    return {"clips": [ClipResult.model_validate(c) for c in clips]}


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
