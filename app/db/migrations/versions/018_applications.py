"""Create applications table for Kanban tracker

Revision ID: 018_applications
Revises: 017_saved_jobs
Create Date: 2026-03-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '018_applications'
down_revision = '017_saved_jobs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'applications',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', sa.String(255), nullable=False, index=True),
        sa.Column('company', sa.String(255), nullable=False),
        sa.Column('role', sa.String(255), nullable=False),
        sa.Column('date_applied', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source_channel', sa.String(100), nullable=False),
        sa.Column('stage', sa.String(50), nullable=False, server_default='applied', index=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('url', sa.String(2000), nullable=True),
        sa.Column('salary', sa.String(255), nullable=True),
        sa.Column('contact_name', sa.String(255), nullable=True),
        sa.Column('contact_email', sa.String(255), nullable=True),
        sa.Column('interview_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('offer_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('job_run_id', UUID(as_uuid=True), sa.ForeignKey('job_runs.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # Composite index for board queries: user + stage
    op.create_index('ix_applications_user_stage', 'applications', ['user_id', 'stage'])


def downgrade() -> None:
    op.drop_index('ix_applications_user_stage', table_name='applications')
    op.drop_table('applications')
