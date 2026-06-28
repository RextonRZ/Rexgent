import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class NarrativeMemorySnapshot(Base):
    __tablename__ = "narrative_memory_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    stage = Column(String(50), nullable=False)
    graph_json = Column(JSONB, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
