import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, ForeignKey, JSON
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
    # which bible references conditioned this clip ([{url, role, character?}])
    # and the deterministic seed it rendered with — consistency, provable
    references_json = Column(JSON, nullable=True)
    seed = Column(Integer, nullable=True)
    status = Column(String(20), default="PENDING")
    # bed_decision's verdict {mute, volume}: computed once, read by both the
    # editor preview and the export worker so they can never disagree
    audio_json = Column(JSON, nullable=True)
    retries = Column(Integer, default=0)
    # editor trim points — honored by EVERY later export, not just the one
    # where the user set them
    trim_start = Column(Float, nullable=True)
    trim_end = Column(Float, nullable=True)
    # small extracted still: outlives the clip URL's expiry (dashboards,
    # analytics evidence)
    poster_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("GenerationJob", back_populates="clips")
    shot = relationship("Shot", back_populates="generated_clips")
    edit_flags = relationship("EditFlag", back_populates="clip", cascade="all, delete-orphan")
