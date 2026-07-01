from pydantic import BaseModel
from uuid import UUID
from typing import Optional, Any


class ExportRequest(BaseModel):
    project_id: UUID
    job_id: UUID
    # Explicit clip order chosen in the editor; when omitted, the worker uses
    # the AI default (best clip per shot, in shot order).
    clip_ids: Optional[list[UUID]] = None
    # Optional music track mixed into the final render.
    audio_url: Optional[str] = None
    audio_volume: float = 1.0      # 1.0 = 100%
    audio_fade_in: float = 0.0     # seconds
    audio_fade_out: float = 0.0    # seconds


class ExportResult(BaseModel):
    id: UUID
    url: Optional[str] = None
    duration_seconds: Optional[float] = None
    caption_url: Optional[str] = None
    report_json: Optional[dict[str, Any]] = None

    model_config = {"from_attributes": True}
