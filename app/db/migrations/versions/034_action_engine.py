"""Add action engine table

New table:
  - action_recommendations: stores generated actions with lifecycle tracking

Revision ID: 034_action_engine
Revises: 033_signal_intelligence_layer
Create Date: 2026-05-01
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "034_action_engine"
down_revision = "033_signal_intelligence_layer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "action_recommendations",
        # ── Primary key + timestamps ────────────────────────────────
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        # ── Owner ───────────────────────────────────────────────────
        sa.Column("user_id", sa.String(255), nullable=False, index=True),
        # ── Source links ────────────────────────────────────────────
        sa.Column(
            "signal_id", UUID(as_uuid=True), nullable=False, index=True,
        ),
        sa.Column(
            "interpretation_id", UUID(as_uuid=True), nullable=True,
        ),
        # ── Action type ─────────────────────────────────────────────
        sa.Column("action_type", sa.String(50), nullable=False, index=True),
        # ── Target ──────────────────────────────────────────────────
        sa.Column("target_name", sa.String(255), nullable=True),
        sa.Column("target_title", sa.String(255), nullable=True),
        sa.Column("target_company", sa.String(255), nullable=False),
        # ── Content ─────────────────────────────────────────────────
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("message_subject", sa.String(500), nullable=True),
        sa.Column("message_body", sa.Text, nullable=False),
        # ── Timing ──────────────────────────────────────────────────
        sa.Column(
            "timing_label", sa.String(50), nullable=False,
            server_default="this_week",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        # ── Scoring ─────────────────────────────────────────────────
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="50"),
        sa.Column("decision_score", sa.Float, nullable=True),
        # ── Lifecycle ───────────────────────────────────────────────
        sa.Column(
            "status", sa.String(20), nullable=False,
            server_default="generated", index=True,
        ),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        # ── Metadata ────────────────────────────────────────────────
        sa.Column(
            "channel_metadata", JSONB, nullable=True,
            server_default="{}",
        ),
        sa.Column(
            "response_data", JSONB, nullable=True,
            server_default="{}",
        ),
        # ── Flags ───────────────────────────────────────────────────
        sa.Column(
            "is_user_edited", sa.Boolean, nullable=False,
            server_default="false",
        ),
    )

    # Composite index for common query patterns
    op.create_index(
        "ix_action_recommendations_user_status",
        "action_recommendations",
        ["user_id", "status"],
    )
    op.create_index(
        "ix_action_recommendations_user_priority",
        "action_recommendations",
        ["user_id", "priority", "confidence"],
    )


def downgrade() -> None:
    op.drop_index("ix_action_recommendations_user_priority")
    op.drop_index("ix_action_recommendations_user_status")
    op.drop_table("action_recommendations")
