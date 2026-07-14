import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.database import Base


class Character(Base):
    __tablename__ = "characters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=True)
    gender = Column(String(50), nullable=True)
    estimated_age = Column(String(50), nullable=True)
    physical_description = Column(Text, nullable=True)
    personality_summary = Column(Text, nullable=True)
    mbti = Column(String(10), nullable=True)
    mbti_confidence = Column(Integer, nullable=True)
    speech_pattern = Column(String(100), nullable=True)
    emotional_arc = Column(JSONB, nullable=True)
    face_embedding = Column(JSONB, nullable=True)   # Qwen-VL text description (keywords/notes)
    face_vector = Column(Vector(512), nullable=True)  # real ArcFace embedding
    reference_image_url = Column(String(500), nullable=True)
    plate_status = Column(String(20), default="ai_pending")
    visual_description = Column(Text, nullable=True)
    video_prompt_fragment = Column(Text, nullable=True)
    face_keywords = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="characters")
    relationships_from = relationship("CharacterRelationship", foreign_keys="CharacterRelationship.from_char_id", back_populates="from_character", cascade="all, delete-orphan")
    relationships_to = relationship("CharacterRelationship", foreign_keys="CharacterRelationship.to_char_id", back_populates="to_character", cascade="all, delete-orphan")
    costume_variants = relationship("CostumeVariant", back_populates="character", cascade="all, delete-orphan")
