import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class CostEvent(Base):
    __tablename__ = "cost_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(20), nullable=False)     # llm | image | video | tts
    stage = Column(String(20), nullable=True)         # casting | audio | generation | export | script | <llm task>
    unit = Column(String(20), nullable=True)          # tokens | image | second | char
    quantity = Column(Float, nullable=True)
    amount_usd = Column(Float, nullable=False, default=0.0)
    ref_id = Column(String(64), nullable=True)
    # LLM events: which model ran and the in/out token split (token dashboard)
    model = Column(String(32), nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
