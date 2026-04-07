"""Create email_intelligence table for deep scan results

Revision ID: 026_email_intelligence
Revises: 025_interview_coach
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '026_email_intelligence'
down_revision = '025_interview_coach'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'email_intelligence',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('scan_status', sa.String(30), nullable=False, server_default='pending'),
        sa.Column('scan_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scan_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scan_period_years', sa.Integer, nullable=False, server_default='5'),
        sa.Column('total_emails_scanned', sa.Integer, nullable=False, server_default='0'),
        sa.Column('job_emails_found', sa.Integer, nullable=False, server_default='0'),
        sa.Column('applications_reconstructed', sa.Integer, nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('reconstructed_timeline', JSONB, nullable=True),
        sa.Column('patterns', JSONB, nullable=True),
        sa.Column('industry_breakdown', JSONB, nullable=True),
        sa.Column('insights', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('email_intelligence')
