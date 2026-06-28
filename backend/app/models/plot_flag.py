import uuid
from sqlalchemy import Column, String, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class PlotFlag(Base):
    __tablename__ = "plot_flags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    script_id = Column(UUID(as_uuid=True), ForeignKey("scripts.id", ondelete="CASCADE"), nullable=False)
    scene_id = Column(UUID(as_uuid=True), ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True)
    flag_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    scene_number = Column(Integer, nullable=True)
    description = Column(Text, nullable=False)
    evidence = Column(Text, nullable=True)
    suggestion = Column(Text, nullable=True)
    status = Column(String(20), default="OPEN")

    script = relationship("Script", back_populates="plot_flags")
