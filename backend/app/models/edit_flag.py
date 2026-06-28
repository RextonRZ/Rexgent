import uuid
from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class EditFlag(Base):
    __tablename__ = "edit_flags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clip_id = Column(UUID(as_uuid=True), ForeignKey("generated_clips.id", ondelete="CASCADE"), nullable=False)
    flag_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    description = Column(Text, nullable=False)
    direction = Column(Text, nullable=True)
    status = Column(String(20), default="OPEN")

    clip = relationship("GeneratedClip", back_populates="edit_flags")
