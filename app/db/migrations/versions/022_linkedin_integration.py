"""Create linkedin_connections and linkedin_conversations tables

Revision ID: 022_linkedin_integration
Revises: 021_calendar_followup_crm
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '022_linkedin_integration'
down_revision = '021_calendar_followup_crm'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── linkedin_connections ──────────────────────────────────────────────
    op.create_table(
        'linkedin_connections',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', sa.String(255), nullable=False, index=True),
        sa.Column('linkedin_id', sa.String(255), nullable=True),
        sa.Column('linkedin_url', sa.String(500), nullable=True),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('headline', sa.String(500), nullable=True),
        sa.Column('current_title', sa.String(255), nullable=True),
        sa.Column('current_company', sa.String(255), nullable=True),
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('profile_image_url', sa.String(500), nullable=True),
        sa.Column('connected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_recruiter', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('is_hiring_manager', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('relationship_strength', sa.String(20), nullable=True),
        sa.Column('tags', JSONB, nullable=True),
        sa.Column('matched_application_id', UUID(as_uuid=True), sa.ForeignKey('applications.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # Dedup: one connection per LinkedIn profile per user
    op.create_index('ix_linkedin_conn_user_lid', 'linkedin_connections', ['user_id', 'linkedin_id'], unique=True)
    # Fast recruiter queries
    op.create_index('ix_linkedin_conn_recruiter', 'linkedin_connections', ['user_id', 'is_recruiter'])
    # Company matching
    op.create_index('ix_linkedin_conn_company', 'linkedin_connections', ['user_id', 'current_company'])

    # ── linkedin_conversations ────────────────────────────────────────────
    op.create_table(
        'linkedin_conversations',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', sa.String(255), nullable=False, index=True),
        sa.Column('connection_id', UUID(as_uuid=True), sa.ForeignKey('linkedin_connections.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('thread_id', sa.String(255), nullable=True),
        sa.Column('direction', sa.String(10), nullable=False),
        sa.Column('sender_name', sa.String(255), nullable=False),
        sa.Column('message_text', sa.Text, nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('application_id', UUID(as_uuid=True), sa.ForeignKey('applications.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_linkedin_conv_thread', 'linkedin_conversations', ['user_id', 'thread_id'])


def downgrade() -> None:
    op.drop_index('ix_linkedin_conv_thread', table_name='linkedin_conversations')
    op.drop_table('linkedin_conversations')
    op.drop_index('ix_linkedin_conn_company', table_name='linkedin_connections')
    op.drop_index('ix_linkedin_conn_recruiter', table_name='linkedin_connections')
    op.drop_index('ix_linkedin_conn_user_lid', table_name='linkedin_connections')
    op.drop_table('linkedin_connections')
