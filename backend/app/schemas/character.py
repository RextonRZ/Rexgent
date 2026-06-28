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
    created_at: datetime

    model_config = {"from_attributes": True}
