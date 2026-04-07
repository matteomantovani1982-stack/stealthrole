"""Create credit_balances and credit_transactions tables

Revision ID: 029_credits
Revises: 028_user_intelligence
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '029_credits'
down_revision = '028_user_intelligence'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'credit_balances',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('balance', sa.Integer, nullable=False, server_default='0'),
        sa.Column('lifetime_purchased', sa.Integer, nullable=False, server_default='0'),
        sa.Column('lifetime_spent', sa.Integer, nullable=False, server_default='0'),
        sa.Column('lifetime_earned', sa.Integer, nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'credit_transactions',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', sa.String(255), nullable=False, index=True),
        sa.Column('transaction_type', sa.String(30), nullable=False),
        sa.Column('amount', sa.Integer, nullable=False),
        sa.Column('balance_after', sa.Integer, nullable=False),
        sa.Column('action', sa.String(50), nullable=True),
        sa.Column('reference_id', sa.String(255), nullable=True),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_credit_tx_user_type', 'credit_transactions', ['user_id', 'transaction_type'])


def downgrade() -> None:
    op.drop_index('ix_credit_tx_user_type', table_name='credit_transactions')
    op.drop_table('credit_transactions')
    op.drop_table('credit_balances')
