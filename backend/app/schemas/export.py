from pydantic import BaseModel
from uuid import UUID
from typing import Optional, Any


class ExportRequest(BaseModel):
    project_id: UUID
    job_id: UUID
    # Explicit clip order chosen in the editor; when omitted, the worker uses
    # the AI default (best clip per shot, in shot order).
    clip_ids: Optional[list[UUID]] = None


class ExportResult(BaseModel):
    id: UUID
    url: Optional[str] = None
    duration_seconds: Optional[float] = None
    caption_url: Optional[str] = None
    report_json: Optional[dict[str, Any]] = None

    model_config = {"from_attributes": True}
