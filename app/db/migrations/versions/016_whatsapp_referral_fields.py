"""Add WhatsApp and referral fields to users

Revision ID: 016
Revises: 015
Create Date: 2026-03-19
"""
from alembic import op
import sqlalchemy as sa

revision = '016_whatsapp_referral_fields'
down_revision = '015_notification_preferences'
branch_labels = None
depends_on = None

_COLUMNS = [
    ("whatsapp_number", sa.String(20), None),
    ("whatsapp_verified", sa.Boolean(), "false"),
    ("whatsapp_alert_mode", sa.String(20), "'OFF'"),
    ("whatsapp_weekly_quota_used", sa.Integer(), "0"),
    ("whatsapp_weekly_quota_limit", sa.Integer(), "2"),
    ("referral_code", sa.String(20), None),
    ("referred_by", sa.String(255), None),
    ("referral_credits_granted", sa.Integer(), "0"),
]


def upgrade() -> None:
    conn = op.get_bind()

    for col_name, col_type, server_default in _COLUMNS:
        result = conn.execute(sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'users' AND column_name = :col"
        ), {"col": col_name})
        if result.fetchone() is None:
            col = sa.Column(
                col_name,
                col_type,
                nullable=True,
                server_default=sa.text(server_default) if server_default else None,
            )
            op.add_column('users', col)

    # Unique index on referral_code (idempotent)
    conn.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_referral_code "
        "ON users (referral_code) WHERE referral_code IS NOT NULL"
    ))


def downgrade() -> None:
    op.drop_index('ix_users_referral_code', table_name='users')
    for col_name, _, _ in reversed(_COLUMNS):
        op.drop_column('users', col_name)
