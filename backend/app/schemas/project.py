from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class ProjectCreate(BaseModel):
    title: str
    genre: Optional[str] = None
    premise: Optional[str] = None


class ProjectResponse(BaseModel):
    id: UUID
    title: str
    genre: Optional[str] = None
    premise: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
