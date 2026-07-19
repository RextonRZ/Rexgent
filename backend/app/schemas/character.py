from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, Any


class CharacterCreate(BaseModel):
    project_id: UUID
    name: str
    role: Optional[str] = None
    gender: Optional[str] = None
    estimated_age: Optional[str] = None
    physical_description: Optional[str] = None


class CharacterResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    role: Optional[str] = None
    gender: Optional[str] = None
    estimated_age: Optional[str] = None
    physical_description: Optional[str] = None
    personality_summary: Optional[str] = None
    mbti: Optional[str] = None
    mbti_confidence: Optional[int] = None
    speech_pattern: Optional[str] = None
    emotional_arc: Optional[dict[str, Any]] = None
    reference_image_url: Optional[str] = None
    visual_description: Optional[str] = None
    video_prompt_fragment: Optional[str] = None
    face_keywords: Optional[list[str]] = None
    # "ref_rejected" = the uploaded photo was refused by the image service's
    # content filter (recognizable public figure) — warn before casting money
    plate_status: Optional[str] = None
    # non-human cast member (computed by the router from the descriptions, not
    # a DB column): the Characters page splits humans from creatures at FIRST
    # paint with this — waiting for the casting bible made the pet visibly
    # jump sections when the bible query landed later
    creature: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}
