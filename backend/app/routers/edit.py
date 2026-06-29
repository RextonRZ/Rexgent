import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.generated_clip import GeneratedClip
from app.models.edit_flag import EditFlag
from app.schemas.edit import TrimRequest, FlagRequest, RegenRequest
from app.services.regen_prompt_rewriter import RegenPromptRewriter
from app.services.qwen_client import QwenClient
from app.config import get_settings

router = APIRouter(prefix="/api/edit", tags=["edit"])


@router.post("/trim")
async def trim_clip(request: TrimRequest, db: Session = Depends(get_db)):
    clip = db.query(GeneratedClip).filter(GeneratedClip.id == request.clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    # Trim points are recorded; FFmpeg trim happens at final render (File 17).
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

    rewriter = RegenPromptRewriter()
    rewrite = await rewriter.rewrite(
        original_prompt=clip.prompt or "",
        flag_description=flag.description,
        flag_type=flag.flag_type,
    )
    revised_prompt = rewrite.get("revised_prompt", clip.prompt)

    qwen = QwenClient(get_settings())
    task_id = await qwen.generate_video_happyhorse(
        prompt=revised_prompt,
        duration=5,
        mode="v2v" if clip.url else "t2v",
        source_video_url=clip.url,
        edit_instruction=flag.description,
    )
    new_url = await qwen.poll_video_task(task_id)

    new_clip = GeneratedClip(
        job_id=clip.job_id, shot_id=clip.shot_id, model_used="happyhorse-v2v",
        prompt=revised_prompt, url=new_url, status="PENDING_REVIEW", retries=0,
    )
    db.add(new_clip)
    flag.status = "REGENERATING"
    db.commit()
    db.refresh(new_clip)

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
