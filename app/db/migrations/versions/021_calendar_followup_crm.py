"""Create application_timeline + calendar_events tables for CRM

Revision ID: 021_calendar_followup_crm
Revises: 020_hidden_market_upgrade
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '021_calendar_followup_crm'
down_revision = '020_hidden_market_upgrade'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── application_timeline ──────────────────────────────────────────────
    op.create_table(
        'application_timeline',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('application_id', UUID(as_uuid=True), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('contact_person', sa.String(255), nullable=True),
        sa.Column('contact_email', sa.String(255), nullable=True),
        sa.Column('contact_role', sa.String(255), nullable=True),
        sa.Column('next_action', sa.String(500), nullable=True),
        sa.Column('next_action_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('follow_up_sent', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('source', sa.String(50), nullable=True),
        sa.Column('source_ref', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # Index for reminder queries: find events with pending follow-ups
    op.create_index('ix_timeline_followup', 'application_timeline', ['next_action_date', 'follow_up_sent'])

    # ── calendar_events ───────────────────────────────────────────────────
    op.create_table(
        'calendar_events',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', sa.String(255), nullable=False, index=True),
        sa.Column('email_account_id', UUID(as_uuid=True), sa.ForeignKey('email_accounts.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('provider_event_id', sa.String(500), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('location', sa.String(500), nullable=True),
        sa.Column('organizer_email', sa.String(255), nullable=True),
        sa.Column('attendees', sa.Text, nullable=True),
        sa.Column('detected_company', sa.String(255), nullable=True),
        sa.Column('detected_role', sa.String(255), nullable=True),
        sa.Column('interview_round', sa.String(50), nullable=True),
        sa.Column('application_id', UUID(as_uuid=True), sa.ForeignKey('applications.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('is_dismissed', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # Dedup: one event per provider per account
    op.create_index('ix_calendar_events_dedup', 'calendar_events', ['email_account_id', 'provider_event_id'], unique=True)

    # ── Add calendar scopes flag to email_accounts ────────────────────────
    op.add_column('email_accounts', sa.Column(
        'calendar_enabled', sa.Boolean, nullable=False, server_default='false',
        comment='Whether this account also has calendar read access',
    ))


def downgrade() -> None:
    op.drop_column('email_accounts', 'calendar_enabled')
    op.drop_index('ix_calendar_events_dedup', table_name='calendar_events')
    op.drop_table('calendar_events')
    op.drop_index('ix_timeline_followup', table_name='application_timeline')
    op.drop_table('application_timeline')
