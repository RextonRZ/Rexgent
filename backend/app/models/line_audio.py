import uuid
from sqlalchemy import Column, String, Text, Integer, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class LineAudio(Base):
    __tablename__ = "line_audio"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    scene_number = Column(Integer, nullable=False)
    line_index = Column(Integer, nullable=False)
    character_name = Column(String(255), nullable=True)
    text = Column(Text, nullable=True)
    voice_id = Column(String(255), nullable=True)
    audio_url = Column(String(500), nullable=True)
    duration_seconds = Column(Float, nullable=True)
