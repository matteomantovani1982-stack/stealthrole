"""Add shadow_applications table

Revision ID: 012
Revises: 011
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '012_shadow_applications'
down_revision = '011_scout_results'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'shadow_applications',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.String(255), nullable=False, index=True),
        sa.Column('profile_id', UUID(as_uuid=True), nullable=True),
        sa.Column('cv_id', UUID(as_uuid=True), nullable=True),

        # Signal context
        sa.Column('company', sa.String(255), nullable=False, index=True),
        sa.Column('signal_type', sa.String(50), nullable=False),
        sa.Column('signal_context', sa.Text(), nullable=True),
        sa.Column('hidden_signal_id', UUID(as_uuid=True), nullable=True),
        sa.Column('radar_opportunity_id', sa.String(255), nullable=True),
        sa.Column('radar_score', sa.Integer(), nullable=True),

        # Generated outputs
        sa.Column('hypothesis_role', sa.String(255), nullable=True),
        sa.Column('hiring_hypothesis', sa.Text(), nullable=True),
        sa.Column('strategy_memo', sa.Text(), nullable=True),
        sa.Column('outreach_linkedin', sa.Text(), nullable=True),
        sa.Column('outreach_email', sa.Text(), nullable=True),
        sa.Column('outreach_followup', sa.Text(), nullable=True),

        # Tailored CV
        sa.Column('tailored_cv_s3_key', sa.String(1000), nullable=True),
        sa.Column('tailored_cv_s3_bucket', sa.String(255), nullable=True),

        # Scoring
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('reasoning', sa.Text(), nullable=True),

        # Lifecycle
        sa.Column('status', sa.String(20), nullable=False, server_default='generating', index=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('celery_task_id', sa.String(255), nullable=True),

        # Tracking
        sa.Column('pipeline_stage', sa.String(20), nullable=True, server_default='created'),
        sa.Column('pipeline_notes', sa.Text(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('shadow_applications')
