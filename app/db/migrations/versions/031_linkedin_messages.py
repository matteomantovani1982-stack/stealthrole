"""Add linkedin_messages table for Feature 2 — conversation-centric sync

Revision ID: 031_linkedin_messages
Revises: 030_mutual_connections
Create Date: 2026-04-15

Stores one row per LinkedIn conversation thread, with all messages embedded
as JSONB. Distinct from the existing linkedin_conversations table (which is
flat, one row per message). Powers Feature 2 of the Chrome extension rebuild.

Classification columns are populated by a Celery task gated behind
ENABLE_LINKEDIN_MSG_CLASSIFY env var — default off, so migrations don't
require any new infra to be wired up.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "031_linkedin_messages"
down_revision = "030_mutual_connections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "linkedin_messages",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("conversation_urn", sa.String(255), nullable=False),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("contact_linkedin_id", sa.String(255), nullable=True),
        sa.Column("contact_linkedin_url", sa.String(500), nullable=True),
        sa.Column("contact_title", sa.String(255), nullable=True),
        sa.Column("contact_company", sa.String(255), nullable=True),
        sa.Column("messages", JSONB, nullable=False),
        sa.Column("message_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sender", sa.String(10), nullable=True),
        sa.Column("is_unread", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("days_since_reply", sa.Integer, nullable=True),
        sa.Column("is_job_related", sa.Boolean, nullable=True),
        sa.Column("classification", sa.String(50), nullable=True),
        sa.Column("stage", sa.String(50), nullable=True),
        sa.Column("ai_draft_reply", sa.Text, nullable=True),
        sa.Column("classification_confidence", sa.Float, nullable=True),
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_linkedin_messages_user_id", "linkedin_messages", ["user_id"])
    op.create_index("ix_linkedin_messages_contact_linkedin_id", "linkedin_messages", ["contact_linkedin_id"])
    op.create_index("ix_linkedin_messages_contact_company", "linkedin_messages", ["contact_company"])
    op.create_index("ix_linkedin_messages_last_message_at", "linkedin_messages", ["last_message_at"])
    op.create_index(
        "ix_linkedin_messages_user_urn",
        "linkedin_messages",
        ["user_id", "conversation_urn"],
        unique=True,
    )
    op.create_index(
        "ix_linkedin_messages_user_last_msg",
        "linkedin_messages",
        ["user_id", "last_message_at"],
    )
    op.create_index(
        "ix_linkedin_messages_user_job_related",
        "linkedin_messages",
        ["user_id", "is_job_related"],
    )


def downgrade() -> None:
    op.drop_index("ix_linkedin_messages_user_job_related", table_name="linkedin_messages")
    op.drop_index("ix_linkedin_messages_user_last_msg", table_name="linkedin_messages")
    op.drop_index("ix_linkedin_messages_user_urn", table_name="linkedin_messages")
    op.drop_index("ix_linkedin_messages_last_message_at", table_name="linkedin_messages")
    op.drop_index("ix_linkedin_messages_contact_company", table_name="linkedin_messages")
    op.drop_index("ix_linkedin_messages_contact_linkedin_id", table_name="linkedin_messages")
    op.drop_index("ix_linkedin_messages_user_id", table_name="linkedin_messages")
    op.drop_table("linkedin_messages")
