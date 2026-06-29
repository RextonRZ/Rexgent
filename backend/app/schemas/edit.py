from pydantic import BaseModel
from uuid import UUID
from typing import Optional


class TrimRequest(BaseModel):
    clip_id: UUID
    start_seconds: float
    end_seconds: float


class FlagRequest(BaseModel):
    clip_id: UUID
    flag_type: str  # APPEARANCE|ACTION|LIGHTING|AUDIO|TIMING|OTHER
    severity: str   # MINOR|MAJOR|REGENERATE_FULLY
    description: str
    direction: Optional[str] = None


class RegenRequest(BaseModel):
    clip_id: UUID
    flag_id: UUID
