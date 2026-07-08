import asyncio
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.generated_clip import GeneratedClip
from app.models.edit_flag import EditFlag
from app.models.generation_job import GenerationJob
from app.schemas.edit import TrimRequest, FlagRequest, RegenRequest
from app.services.regen_prompt_rewriter import RegenPromptRewriter
from app.services.clip_store import persist_clip_url
from app.services.qwen_client import QwenClient
from app.config import get_settings

from app.deps import get_current_user

router = APIRouter(prefix="/api/edit", tags=["edit"],
                   # every pipeline endpoint requires a signed-in user
                   dependencies=[Depends(get_current_user)])


@router.post("/trim")
async def trim_clip(request: TrimRequest, db: Session = Depends(get_db)):
    clip = db.query(GeneratedClip).filter(GeneratedClip.id == request.clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    # Persisted on the clip so ANY later export honors the trim (the FFmpeg
    # cut itself happens at final render).
    clip.trim_start = request.start_seconds
    clip.trim_end = request.end_seconds
    db.commit()
    return {
        "clip_id": str(clip.id),
        "start": request.start_seconds,
        "end": request.end_seconds,
        "status": "trim_recorded",
    }


@router.post("/flag")
async def flag_clip(request: FlagRequest, db: Session = Depends(get_db)):
    clip = db.query(GeneratedClip).filter(GeneratedClip.id == request.clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    flag = EditFlag(
        clip_id=request.clip_id,
        flag_type=request.flag_type,
        severity=request.severity,
        description=request.description,
        direction=request.direction,
    )
    db.add(flag)
    db.commit()
    db.refresh(flag)
    return {"flag_id": str(flag.id), "status": "OPEN"}


@router.post("/regen")
async def regen_clip(request: RegenRequest, db: Session = Depends(get_db)):
    clip = db.query(GeneratedClip).filter(GeneratedClip.id == request.clip_id).first()
    flag = db.query(EditFlag).filter(EditFlag.id == request.flag_id).first()
    if not clip or not flag:
        raise HTTPException(status_code=404, detail="Clip or flag not found")

    job = db.query(GenerationJob).filter(GenerationJob.id == clip.job_id).first()
    from app.websocket.tool_events import tool_event
    if job:
        tool_event(str(job.project_id), "generate", "fix_take", "started", agent="Editor")
    rewriter = RegenPromptRewriter()
    if job:
        from app.services.usage_tracker import track_project
        with track_project(job.project_id, db):
            rewrite = await rewriter.rewrite(
                original_prompt=clip.prompt or "",
                flag_description=flag.description,
                flag_type=flag.flag_type,
            )
    else:
        rewrite = await rewriter.rewrite(
            original_prompt=clip.prompt or "",
            flag_description=flag.description,
            flag_type=flag.flag_type,
        )
    revised_prompt = rewrite.get("revised_prompt", clip.prompt)

    # the re-render must be as long as the ORIGINAL shot — a hardcoded 5s
    # regen of a 10s dialogue shot would be too short to hold its line
    from app.models.shot import Shot
    shot = db.query(Shot).filter(Shot.id == clip.shot_id).first()
    duration = (shot.estimated_duration_seconds if shot else None) or 5

    qwen = QwenClient(get_settings())
    task_id = await qwen.generate_video_happyhorse(
        prompt=revised_prompt,
        duration=duration,
        mode="v2v" if clip.url else "t2v",
        source_video_url=clip.url,
        edit_instruction=flag.description,
    )
    new_url = await qwen.poll_video_task(task_id)
    # DashScope URLs expire (~24h) — keep our own copy on OSS
    if job:
        new_url = await asyncio.to_thread(
            persist_clip_url, str(job.project_id), f"shot_{clip.shot_id}_regen", new_url)

    new_clip = GeneratedClip(
        job_id=clip.job_id, shot_id=clip.shot_id, model_used="happyhorse-v2v",
        prompt=revised_prompt, url=new_url, status="PENDING_REVIEW", retries=0,
    )
    db.add(new_clip)
    flag.status = "REGENERATING"
    db.commit()
    db.refresh(new_clip)
    if job:
        # the fix-a-take render costs real money — it lands on the ledger too
        from app.services.cost_ledger import record_video
        record_video(db, str(job.project_id), duration, "happyhorse",
                     ref_id=str(new_clip.id),
                     model_name="happyhorse-1.0-video-edit")
    if job:
        tool_event(str(job.project_id), "generate", "fix_take", "succeeded",
                   agent="Editor", artifact="take re-rendered")

    return {
        "new_clip_id": str(new_clip.id),
        "new_url": new_url,
        "original_url": clip.url,
        "changes_made": rewrite.get("changes_made", []),
    }


@router.post("/approve")
async def approve_clip(request: dict, db: Session = Depends(get_db)):
    clip_id = request.get("clip_id")
    clip = db.query(GeneratedClip).filter(GeneratedClip.id == uuid.UUID(clip_id)).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    clip.status = "APPROVED"
    db.commit()
    return {"status": "APPROVED", "clip_id": str(clip.id)}
