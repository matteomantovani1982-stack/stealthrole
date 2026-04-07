"""Add notification_preferences column to users

Revision ID: 015
Revises: 014
Create Date: 2026-03-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '015_notification_preferences'
down_revision = '014_application_events'
branch_labels = None
depends_on = None

_DEFAULT_PREFS = '{"pack_complete_email": true, "scout_digest_email": true, "hidden_market_email": true, "shadow_ready_email": true}'


def upgrade() -> None:
    # Only add if column doesn't already exist
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'users' AND column_name = 'notification_preferences'"
    ))
    if result.fetchone() is None:
        op.add_column(
            'users',
            sa.Column(
                'notification_preferences',
                JSONB(),
                nullable=False,
                server_default=sa.text(f"'{_DEFAULT_PREFS}'::jsonb"),
            ),
        )


def downgrade() -> None:
    op.drop_column('users', 'notification_preferences')
