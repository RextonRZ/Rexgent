import uuid
from sqlalchemy import Column, String, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class CharacterRelationship(Base):
    __tablename__ = "character_relationships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    from_char_id = Column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    to_char_id = Column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    rel_type = Column(String(50), nullable=False)
    strength = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    first_established_scene = Column(Integer, nullable=True)
    evidence_quote = Column(Text, nullable=True)
    evolution = Column(String(50), nullable=True)
    evolution_description = Column(Text, nullable=True)
    # ordered arc of the relationship as it changes: [{scene, type, label}, ...]
    # the last stage's type is the current rel_type shown on the graph
    stages = Column(JSONB, nullable=True)

    from_character = relationship("Character", foreign_keys=[from_char_id], back_populates="relationships_from")
    to_character = relationship("Character", foreign_keys=[to_char_id], back_populates="relationships_to")
