from pydantic import BaseModel
from uuid import UUID
from typing import Optional, Any


class ExportRequest(BaseModel):
    project_id: UUID
    job_id: UUID


class ExportResult(BaseModel):
    id: UUID
    url: Optional[str] = None
    duration_seconds: Optional[float] = None
    caption_url: Optional[str] = None
    report_json: Optional[dict[str, Any]] = None

    model_config = {"from_attributes": True}
