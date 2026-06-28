"""initial schema — all 12 tables

Revision ID: 001
Revises:
Create Date: 2026-06-28
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("genre", sa.String(100), nullable=True),
        sa.Column("premise", sa.Text, nullable=True),
        sa.Column("status", sa.String(50), server_default="draft"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "scripts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_text", sa.Text, nullable=True),
        sa.Column("structured_json", postgresql.JSONB, nullable=True),
        sa.Column("version", sa.Integer, server_default="1"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "scenes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("script_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scripts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.Integer, nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("heading", sa.String(255), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("time_of_day", sa.String(50), nullable=True),
        sa.Column("characters_json", postgresql.JSONB, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("emotional_beat", sa.String(255), nullable=True),
        sa.Column("dialogue_json", postgresql.JSONB, nullable=True),
        sa.Column("stage_directions", postgresql.JSONB, nullable=True),
    )

    op.create_table(
        "characters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=True),
        sa.Column("gender", sa.String(50), nullable=True),
        sa.Column("estimated_age", sa.String(50), nullable=True),
        sa.Column("physical_description", sa.Text, nullable=True),
        sa.Column("personality_summary", sa.Text, nullable=True),
        sa.Column("mbti", sa.String(10), nullable=True),
        sa.Column("mbti_confidence", sa.Integer, nullable=True),
        sa.Column("speech_pattern", sa.String(100), nullable=True),
        sa.Column("emotional_arc", postgresql.JSONB, nullable=True),
        sa.Column("face_embedding", postgresql.JSONB, nullable=True),
        sa.Column("reference_image_url", sa.String(500), nullable=True),
        sa.Column("visual_description", sa.Text, nullable=True),
        sa.Column("video_prompt_fragment", sa.Text, nullable=True),
        sa.Column("face_keywords", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "character_relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_char_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("characters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("to_char_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("characters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rel_type", sa.String(50), nullable=False),
        sa.Column("strength", sa.Integer, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("first_established_scene", sa.Integer, nullable=True),
        sa.Column("evidence_quote", sa.Text, nullable=True),
        sa.Column("evolution", sa.String(50), nullable=True),
        sa.Column("evolution_description", sa.Text, nullable=True),
    )

    op.create_table(
        "plot_flags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("script_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scripts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("flag_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("scene_number", sa.Integer, nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("evidence", sa.Text, nullable=True),
        sa.Column("suggestion", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), server_default="OPEN"),
    )

    op.create_table(
        "shots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scene_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.Integer, nullable=False),
        sa.Column("shot_type", sa.String(20), nullable=True),
        sa.Column("camera_movement", sa.String(50), nullable=True),
        sa.Column("lighting", sa.String(50), nullable=True),
        sa.Column("colour_mood", sa.String(50), nullable=True),
        sa.Column("action", sa.Text, nullable=True),
        sa.Column("dialogue", sa.Text, nullable=True),
        sa.Column("emotional_beat", sa.String(255), nullable=True),
        sa.Column("estimated_duration_seconds", sa.Integer, server_default="5"),
        sa.Column("quality_tier", sa.String(20), nullable=True),
        sa.Column("characters_in_frame", postgresql.JSONB, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("director_note", sa.Text, nullable=True),
    )

    op.create_table(
        "generation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), server_default="PENDING"),
        sa.Column("total_shots", sa.Integer, nullable=True),
        sa.Column("completed_shots", sa.Integer, server_default="0"),
        sa.Column("estimated_cost", sa.Float, nullable=True),
        sa.Column("actual_cost", sa.Float, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "generated_clips",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_used", sa.String(50), nullable=True),
        sa.Column("prompt", sa.Text, nullable=True),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("consistency_score", sa.Float, nullable=True),
        sa.Column("status", sa.String(20), server_default="PENDING"),
        sa.Column("retries", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "edit_flags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("clip_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generated_clips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("flag_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("direction", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), server_default="OPEN"),
    )

    op.create_table(
        "final_exports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column("caption_url", sa.String(500), nullable=True),
        sa.Column("report_json", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "narrative_memory_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("stage", sa.String(50), nullable=False),
        sa.Column("graph_json", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("narrative_memory_snapshots")
    op.drop_table("final_exports")
    op.drop_table("edit_flags")
    op.drop_table("generated_clips")
    op.drop_table("generation_jobs")
    op.drop_table("shots")
    op.drop_table("plot_flags")
    op.drop_table("character_relationships")
    op.drop_table("characters")
    op.drop_table("scenes")
    op.drop_table("scripts")
    op.drop_table("projects")
