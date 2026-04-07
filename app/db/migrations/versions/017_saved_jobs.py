"""Create saved_jobs table

Revision ID: 017_saved_jobs
Revises: 016_whatsapp_referral_fields
Create Date: 2026-03-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '017_saved_jobs'
down_revision = '016_whatsapp_referral_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'saved_jobs',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('external_id', sa.String(255), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('company', sa.String(255), nullable=False, server_default=''),
        sa.Column('location', sa.String(255), nullable=False, server_default=''),
        sa.Column('salary_min', sa.Integer(), nullable=True),
        sa.Column('salary_max', sa.Integer(), nullable=True),
        sa.Column('url', sa.String(2000), nullable=False, server_default=''),
        sa.Column('metadata', JSONB(), nullable=False, server_default='{}'),
        sa.Column('saved_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('user_id', 'source', 'external_id', name='uq_saved_job_user_source_ext'),
    )
    op.create_index('ix_saved_jobs_user_id', 'saved_jobs', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_saved_jobs_user_id')
    op.drop_table('saved_jobs')
