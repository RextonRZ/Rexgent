import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class CostEvent(Base):
    __tablename__ = "cost_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(20), nullable=False)     # llm | image | video | tts
    stage = Column(String(20), nullable=True)         # casting | audio | generation | export | script
    unit = Column(String(20), nullable=True)          # tokens | image | second | char
    quantity = Column(Float, nullable=True)
    amount_usd = Column(Float, nullable=False, default=0.0)
    ref_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
