import uuid
from sqlalchemy import Column, String, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.database import Base


class CostumeVariant(Base):
    __tablename__ = "costume_variants"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    character_id = Column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    label = Column(String(255), nullable=False)
    outfit_description = Column(Text, nullable=True)
    plate_image_url = Column(String(500), nullable=True)
    face_vector = Column(Vector(512), nullable=True)
    scene_numbers = Column(JSONB, nullable=True)   # list[int]
    is_default = Column(Boolean, default=False)
    plate_status = Column(String(20), default="ai_pending")
    character = relationship("Character", back_populates="costume_variants")
