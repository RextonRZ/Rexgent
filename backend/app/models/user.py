import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    persona = Column(String(50), nullable=True)  # onboarding answer
    # Bring-your-own-key: the user's DashScope key, Fernet-encrypted with the
    # server secret. Their dramas bill their own Qwen Cloud account.
    dashscope_key_enc = Column(String(1024), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
