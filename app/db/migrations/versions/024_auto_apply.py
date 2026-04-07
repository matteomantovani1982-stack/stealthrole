"""Create auto_apply_profiles and auto_apply_submissions tables

Revision ID: 024_auto_apply
Revises: 023_relationship_engine
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '024_auto_apply'
down_revision = '023_relationship_engine'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'auto_apply_profiles',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('linkedin_url', sa.String(500), nullable=True),
        sa.Column('website_url', sa.String(500), nullable=True),
        sa.Column('current_company', sa.String(255), nullable=True),
        sa.Column('current_title', sa.String(255), nullable=True),
        sa.Column('standard_answers', JSONB, nullable=False, server_default='{}'),
        sa.Column('cover_letter_template', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'auto_apply_submissions',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', sa.String(255), nullable=False, index=True),
        sa.Column('application_id', UUID(as_uuid=True), sa.ForeignKey('applications.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('job_run_id', UUID(as_uuid=True), sa.ForeignKey('job_runs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('company', sa.String(255), nullable=False),
        sa.Column('role', sa.String(255), nullable=False),
        sa.Column('apply_url', sa.String(2000), nullable=False),
        sa.Column('ats_platform', sa.String(50), nullable=False, server_default='other'),
        sa.Column('form_payload', JSONB, nullable=False, server_default='{}'),
        sa.Column('cv_s3_key', sa.String(1000), nullable=True),
        sa.Column('status', sa.String(30), nullable=False, server_default='prepared', index=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_submissions_user_status', 'auto_apply_submissions', ['user_id', 'status'])


def downgrade() -> None:
    op.drop_index('ix_submissions_user_status', table_name='auto_apply_submissions')
    op.drop_table('auto_apply_submissions')
    op.drop_table('auto_apply_profiles')
