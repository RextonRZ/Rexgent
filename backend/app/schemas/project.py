from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class ProjectCreate(BaseModel):
    title: str
    genre: Optional[str] = None
    premise: Optional[str] = None


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    genre: Optional[str] = None
    premise: Optional[str] = None
    poster_url: Optional[str] = None


class PosterFromClipRequest(BaseModel):
    clip_url: str
    timestamp: float = 0.0


class TitleSuggestRequest(BaseModel):
    premise: str


class ProjectResponse(BaseModel):
    id: UUID
    title: str
    genre: Optional[str] = None
    premise: Optional[str] = None
    status: str
    poster_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
