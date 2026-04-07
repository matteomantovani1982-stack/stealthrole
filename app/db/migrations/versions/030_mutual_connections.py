"""Add mutual_connections table for 2nd-degree path finding

Revision ID: 030_mutual_connections
Revises: 029_credits
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "030_mutual_connections"
down_revision = "029_credits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mutual_connections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.String(255), nullable=False, index=True),
        sa.Column("target_linkedin_id", sa.String(255), nullable=False, index=True),
        sa.Column("target_name", sa.String(255), nullable=False),
        sa.Column("target_title", sa.String(500), nullable=True),
        sa.Column("target_company", sa.String(255), nullable=True, index=True),
        sa.Column("target_linkedin_url", sa.String(500), nullable=True),
        sa.Column("mutual_linkedin_id", sa.String(255), nullable=False),
        sa.Column("mutual_name", sa.String(255), nullable=False),
        sa.Column("mutual_linkedin_url", sa.String(500), nullable=True),
        sa.Column("total_mutual_count", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_mutual_conn_user_target", "mutual_connections", ["user_id", "target_linkedin_id"])


def downgrade() -> None:
    op.drop_table("mutual_connections")
