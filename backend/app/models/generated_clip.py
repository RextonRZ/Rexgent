import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class GeneratedClip(Base):
    __tablename__ = "generated_clips"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False)
    shot_id = Column(UUID(as_uuid=True), ForeignKey("shots.id", ondelete="CASCADE"), nullable=False)
    model_used = Column(String(50), nullable=True)
    prompt = Column(Text, nullable=True)
    url = Column(String(500), nullable=True)
    consistency_score = Column(Float, nullable=True)
    face_score = Column(Float, nullable=True)
    outfit_score = Column(Float, nullable=True)
    background_score = Column(Float, nullable=True)
    status = Column(String(20), default="PENDING")
    retries = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("GenerationJob", back_populates="clips")
    shot = relationship("Shot", back_populates="generated_clips")
    edit_flags = relationship("EditFlag", back_populates="clip", cascade="all, delete-orphan")
