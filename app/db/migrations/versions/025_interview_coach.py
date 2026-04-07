"""Create interview_rounds and compensation_benchmarks tables

Revision ID: 025_interview_coach
Revises: 024_auto_apply
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '025_interview_coach'
down_revision = '024_auto_apply'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'interview_rounds',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('application_id', UUID(as_uuid=True), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', sa.String(255), nullable=False, index=True),
        sa.Column('round_number', sa.Integer, nullable=False, server_default='1'),
        sa.Column('round_type', sa.String(50), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_minutes', sa.Integer, nullable=True),
        sa.Column('interviewer_name', sa.String(255), nullable=True),
        sa.Column('interviewer_title', sa.String(255), nullable=True),
        sa.Column('interviewer_linkedin', sa.String(500), nullable=True),
        sa.Column('prep_notes', sa.Text, nullable=True),
        sa.Column('focus_areas', JSONB, nullable=True),
        sa.Column('debrief', sa.Text, nullable=True),
        sa.Column('questions_asked', JSONB, nullable=True),
        sa.Column('confidence_rating', sa.Integer, nullable=True),
        sa.Column('outcome', sa.String(30), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'compensation_benchmarks',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('role_title', sa.String(255), nullable=False),
        sa.Column('region', sa.String(100), nullable=False),
        sa.Column('seniority_level', sa.String(50), nullable=True),
        sa.Column('currency', sa.String(10), nullable=False, server_default='USD'),
        sa.Column('p25', sa.Integer, nullable=True),
        sa.Column('p50', sa.Integer, nullable=True),
        sa.Column('p75', sa.Integer, nullable=True),
        sa.Column('p90', sa.Integer, nullable=True),
        sa.Column('total_comp_p50', sa.Integer, nullable=True),
        sa.Column('source', sa.String(100), nullable=True),
        sa.Column('sample_size', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_comp_role_region', 'compensation_benchmarks', ['role_title', 'region'])


def downgrade() -> None:
    op.drop_index('ix_comp_role_region', table_name='compensation_benchmarks')
    op.drop_table('compensation_benchmarks')
    op.drop_table('interview_rounds')
