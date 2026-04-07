"""Add hidden_signals table

Revision ID: 013
Revises: 012
Create Date: 2026-03-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '013_hidden_signals'
down_revision = '012_shadow_applications'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'hidden_signals',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('company_name', sa.String(255), nullable=False),
        sa.Column('signal_type', sa.String(50), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('likely_roles', JSONB(), nullable=False, server_default='[]'),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('source_url', sa.String(2000), nullable=True),
        sa.Column('source_name', sa.String(100), nullable=True),
        sa.Column('is_dismissed', sa.Boolean(), nullable=False, server_default='false'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_hidden_signals_user_id', 'hidden_signals', ['user_id'])
    op.create_index('ix_hidden_signals_created_at', 'hidden_signals', [sa.text('created_at DESC')])


def downgrade() -> None:
    op.drop_index('ix_hidden_signals_created_at', table_name='hidden_signals')
    op.drop_index('ix_hidden_signals_user_id', table_name='hidden_signals')
    op.drop_table('hidden_signals')
