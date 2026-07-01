import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.final_export import FinalExport
from app.schemas.export import ExportRequest, ExportResult
from app.services.oss_manager import OSSManager
from app.config import get_settings
from app.workers.export_worker import run_export

router = APIRouter(prefix="/api/export", tags=["export"])


@router.post("/{project_id}/audio")
async def upload_audio(project_id: str, file: UploadFile = File(...)):
    """Upload a music track for the export; returns its public URL."""
    content = await file.read()
    ext = (file.filename or "music.mp3").rsplit(".", 1)[-1].lower()
    if ext not in {"mp3", "wav", "m4a", "aac", "ogg"}:
        ext = "mp3"
    oss = OSSManager(get_settings())
    key = oss.get_project_path(project_id, "exports", f"music.{ext}")
    url = oss.upload_bytes(content, key, content_type=file.content_type or "audio/mpeg")
    return {"url": url}


@router.post("/render")
async def render_export(request: ExportRequest, db: Session = Depends(get_db)):
    # Unified ordered clip list with per-clip trim.
    if request.clips:
        clips = [
            {"id": str(c.clip_id), "in": c.trim_start, "out": c.trim_end}
            for c in request.clips
        ]
    elif request.clip_ids:
        clips = [{"id": str(cid), "in": 0.0, "out": None} for cid in request.clip_ids]
    else:
        clips = None

    audio = None
    if request.audio_url:
        audio = {
            "url": request.audio_url,
            "volume": request.audio_volume,
            "fade_in": request.audio_fade_in,
            "fade_out": request.audio_fade_out,
        }
    run_export.delay(str(request.project_id), str(request.job_id), clips, audio)
    return {"status": "rendering", "message": "Export job started"}


@router.get("/{project_id}/download")
async def get_download(project_id: str, db: Session = Depends(get_db)):
    export = (
        db.query(FinalExport)
        .filter(FinalExport.project_id == uuid.UUID(project_id))
        .order_by(FinalExport.created_at.desc())
        .first()
    )
    if not export:
        raise HTTPException(status_code=404, detail="No export found")

    result = ExportResult.model_validate(export).model_dump()
    result["download_url"] = export.url
    return result
