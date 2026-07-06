import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Boolean, Float, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=True)
    title = Column(String(255), nullable=False)
    genre = Column(String(100), nullable=True)
    premise = Column(Text, nullable=True)
    status = Column(String(50), default="draft")
    poster_url = Column(String(500), nullable=True)
    # per-drama budget the user sets at creation; drives the generation ceiling
    # and the Wan/HappyHorse allocation. token_budget is the hackathon's judged
    # LLM allowance, shown as a target.
    credit_budget = Column(Float, default=40.0)
    token_budget = Column(Integer, default=2_000_000)
    auto_approve_casting = Column(Boolean, default=False)
    auto_clarify = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scripts = relationship("Script", back_populates="project", cascade="all, delete-orphan")
    characters = relationship("Character", back_populates="project", cascade="all, delete-orphan")
    generation_jobs = relationship("GenerationJob", back_populates="project", cascade="all, delete-orphan")
    final_exports = relationship("FinalExport", back_populates="project", cascade="all, delete-orphan")
