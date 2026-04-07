"""Add application_events table

Revision ID: 014
Revises: 013
Create Date: 2026-03-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '014_application_events'
down_revision = '013_hidden_signals'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'application_events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('job_run_id', UUID(as_uuid=True), sa.ForeignKey('job_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_application_events_job_run_id', 'application_events', ['job_run_id'])


def downgrade() -> None:
    op.drop_index('ix_application_events_job_run_id', table_name='application_events')
    op.drop_table('application_events')
