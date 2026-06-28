from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class UUIDModel(BaseModel):
    id: UUID

    model_config = {"from_attributes": True}


class TimestampModel(UUIDModel):
    created_at: datetime


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
