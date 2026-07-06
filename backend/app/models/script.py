import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class Script(Base):
    __tablename__ = "scripts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    raw_text = Column(Text, nullable=True)
    structured_json = Column(JSONB, nullable=True)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="scripts")
    scenes = relationship("Scene", back_populates="script", cascade="all, delete-orphan")
    plot_flags = relationship("PlotFlag", back_populates="script", cascade="all, delete-orphan")


class Scene(Base):
    __tablename__ = "scenes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    script_id = Column(UUID(as_uuid=True), ForeignKey("scripts.id", ondelete="CASCADE"), nullable=False)
    number = Column(Integer, nullable=False)
    title = Column(String(255), nullable=True)
    heading = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    time_of_day = Column(String(50), nullable=True)
    characters_json = Column(JSONB, nullable=True)
    description = Column(Text, nullable=True)
    emotional_beat = Column(String(255), nullable=True)
    dialogue_json = Column(JSONB, nullable=True)
    stage_directions = Column(JSONB, nullable=True)
    # set dressing: {"set_items": [...], "state_changes": [{from_shot, state}]}
    # — props every shot of the scene must render identically, and how the
    # action changes them (a broken vase stays broken)
    set_json = Column(JSONB, nullable=True)

    script = relationship("Script", back_populates="scenes")
    shots = relationship("Shot", back_populates="scene", cascade="all, delete-orphan")
