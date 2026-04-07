"""Create user_intelligence table

Revision ID: 028_user_intelligence
Revises: 027_writing_style
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '028_user_intelligence'
down_revision = '027_writing_style'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_intelligence',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('profile_strength', sa.Integer, nullable=False, server_default='0'),
        sa.Column('strength_breakdown', JSONB, nullable=True),
        sa.Column('behavioral_profile', JSONB, nullable=True),
        sa.Column('success_patterns', JSONB, nullable=True),
        sa.Column('failure_patterns', JSONB, nullable=True),
        sa.Column('recommendations', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('user_intelligence')
