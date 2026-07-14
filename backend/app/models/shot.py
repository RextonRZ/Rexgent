import uuid
from sqlalchemy import Column, String, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class Shot(Base):
    __tablename__ = "shots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scene_id = Column(UUID(as_uuid=True), ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False)
    number = Column(Integer, nullable=False)
    shot_type = Column(String(20), nullable=True)
    camera_movement = Column(String(50), nullable=True)
    lighting = Column(String(50), nullable=True)
    colour_mood = Column(String(50), nullable=True)
    action = Column(Text, nullable=True)
    dialogue = Column(Text, nullable=True)
    emotional_beat = Column(String(255), nullable=True)
    estimated_duration_seconds = Column(Integer, default=5)
    quality_tier = Column(String(20), nullable=True)
    characters_in_frame = Column(JSONB, nullable=True)
    # subset of characters_in_frame that are only a back/shoulder to camera
    # (face unseen). They anchor outfit, not identity, and the shot is really
    # ABOUT the other character(s).
    foreground_characters = Column(JSONB, nullable=True)
    # absolute per-shot geometry: {"subjects": [{character, frame_position,
    # screen_side, facing, eyeline, action}], "reverse_angle": bool} — the
    # stage map enforces screen sides across the scene (180-degree rule)
    blocking_json = Column(JSONB, nullable=True)
    # the crafted prompt engineering: {action, prompt, negative_prompt,
    # environment {behavior, suppressed, source, priority}} written at render
    prompt_json = Column(JSONB, nullable=True)
    # the Director Engine's per-shot cinematic plan: {purpose, lens, composition,
    # intended_duration, transition_in, blocking_delta}. Null on shots boarded
    # without DIRECTOR_ENGINE — read by scene_prompt_craft when present.
    director_json = Column(JSONB, nullable=True)
    notes = Column(Text, nullable=True)
    director_note = Column(Text, nullable=True)

    scene = relationship("Scene", back_populates="shots")
    generated_clips = relationship("GeneratedClip", back_populates="shot", cascade="all, delete-orphan")
