from pydantic import BaseModel
from uuid import UUID
from typing import Optional, Any


class ClipEdit(BaseModel):
    clip_id: Optional[UUID] = None  # a generated clip…
    url: Optional[str] = None       # …or an imported external media URL
    trim_start: float = 0.0
    trim_end: Optional[float] = None  # None = to the end of the clip


class ExportRequest(BaseModel):
    project_id: UUID
    job_id: UUID
    # Ordered clips with per-clip trim, chosen in the editor. When omitted the
    # worker uses the AI default (best clip per shot, in shot order, untrimmed).
    clips: Optional[list[ClipEdit]] = None
    clip_ids: Optional[list[UUID]] = None  # legacy: order only, no trim
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
