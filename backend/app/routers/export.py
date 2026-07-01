import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.final_export import FinalExport
from app.schemas.export import ExportRequest, ExportResult
from app.workers.export_worker import run_export

router = APIRouter(prefix="/api/export", tags=["export"])


@router.post("/render")
async def render_export(request: ExportRequest, db: Session = Depends(get_db)):
    clip_ids = [str(c) for c in request.clip_ids] if request.clip_ids else None
    run_export.delay(str(request.project_id), str(request.job_id), clip_ids)
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
