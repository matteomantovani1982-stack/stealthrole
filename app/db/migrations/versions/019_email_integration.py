"""Create email_accounts and email_scans tables

Revision ID: 019_email_integration
Revises: 018_applications
Create Date: 2026-03-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '019_email_integration'
down_revision = '018_applications'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── email_accounts ────────────────────────────────────────────────────
    op.create_table(
        'email_accounts',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', sa.String(255), nullable=False, index=True),
        sa.Column('provider', sa.String(20), nullable=False),
        sa.Column('email_address', sa.String(255), nullable=False),
        sa.Column('access_token_encrypted', sa.Text, nullable=False),
        sa.Column('refresh_token_encrypted', sa.Text, nullable=True),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sync_status', sa.String(20), nullable=False, server_default='idle'),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sync_error', sa.Text, nullable=True),
        sa.Column('sync_cursor', sa.String(255), nullable=True),
        sa.Column('total_scanned', sa.Integer, nullable=False, server_default='0'),
        sa.Column('total_signals', sa.Integer, nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # One active account per provider per user
    op.create_index(
        'ix_email_accounts_user_provider',
        'email_accounts', ['user_id', 'provider'],
        unique=True,
    )

    # ── email_scans ───────────────────────────────────────────────────────
    op.create_table(
        'email_scans',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('email_account_id', UUID(as_uuid=True), sa.ForeignKey('email_accounts.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('message_id', sa.String(255), nullable=False),
        sa.Column('email_from', sa.String(255), nullable=False),
        sa.Column('email_subject', sa.String(1000), nullable=False),
        sa.Column('email_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('email_snippet', sa.Text, nullable=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('role', sa.String(255), nullable=True),
        sa.Column('detected_stage', sa.String(50), nullable=False, server_default='unknown'),
        sa.Column('confidence', sa.String(20), nullable=False, server_default='medium'),
        sa.Column('application_id', UUID(as_uuid=True), sa.ForeignKey('applications.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('is_dismissed', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # Dedup: one scan per message per account
    op.create_index(
        'ix_email_scans_account_message',
        'email_scans', ['email_account_id', 'message_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('ix_email_scans_account_message', table_name='email_scans')
    op.drop_table('email_scans')
    op.drop_index('ix_email_accounts_user_provider', table_name='email_accounts')
    op.drop_table('email_accounts')
