import uuid
from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class StylePreset(Base):
    __tablename__ = "style_presets"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False)
    style_tags = Column(JSONB, nullable=True)      # list[str]
    free_text = Column(Text, nullable=True)
    plate_image_url = Column(String(500), nullable=True)
    negative_prompt = Column(Text, nullable=True)
