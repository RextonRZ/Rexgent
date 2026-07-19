from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class ProjectCreate(BaseModel):
    title: str
    genre: Optional[str] = None
    premise: Optional[str] = None
    credit_budget: Optional[float] = None
    token_budget: Optional[int] = None
    video_ratio: Optional[str] = None  # "9:16" (default) | "16:9"
    episode_count: Optional[int] = None
    target_length: Optional[int] = None  # seconds per episode
    visual_style: Optional[str] = None  # style_catalog key; None = photoreal


class BudgetEstimateRequest(BaseModel):
    episode_count: int = 1
    target_length: int = 30  # seconds per episode
    characters: int = 4


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    genre: Optional[str] = None
    premise: Optional[str] = None
    poster_url: Optional[str] = None
    credit_budget: Optional[float] = None  # raise the spend cap mid-flight
    video_ratio: Optional[str] = None      # "9:16" | "16:9"
    episode_count: Optional[int] = None
    target_length: Optional[int] = None   # seconds per episode
    visual_style: Optional[str] = None    # catalog key; "photoreal" clears it


class PosterFromClipRequest(BaseModel):
    clip_url: str
    timestamp: float = 0.0
    # vertical crop focus (0..100, percent from the top) for portrait clips:
    # the poster is cropped server-side to the card's 16:10 window at this
    # height, so what the picker previews is what the card shows
    focus_y: float = 25.0


class TitleSuggestRequest(BaseModel):
    premise: str


class ProjectResponse(BaseModel):
    id: UUID
    title: str
    genre: Optional[str] = None
    premise: Optional[str] = None
    status: str
    poster_url: Optional[str] = None
    credit_budget: Optional[float] = None
    token_budget: Optional[int] = None
    video_ratio: Optional[str] = None
    episode_count: Optional[int] = None
    target_length: Optional[int] = None
    visual_style: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
