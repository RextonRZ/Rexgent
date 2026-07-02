import uuid
from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class LocationPlate(Base):
    __tablename__ = "location_plates"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    location_key = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    plate_image_url = Column(String(500), nullable=True)
    scene_numbers = Column(JSONB, nullable=True)   # list[int]
