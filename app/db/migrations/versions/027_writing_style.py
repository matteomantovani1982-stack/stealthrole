"""Add writing_style to email_intelligence

Revision ID: 027_writing_style
Revises: 026_email_intelligence
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '027_writing_style'
down_revision = '026_email_intelligence'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('email_intelligence', sa.Column(
        'writing_style', JSONB, nullable=True,
        comment='Extracted writing style from outgoing emails',
    ))


def downgrade() -> None:
    op.drop_column('email_intelligence', 'writing_style')
