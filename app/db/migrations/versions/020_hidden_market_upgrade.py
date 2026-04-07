"""Upgrade hidden_signals with structured signal data + evidence tier

Revision ID: 020_hidden_market_upgrade
Revises: 019_email_integration
Create Date: 2026-03-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '020_hidden_market_upgrade'
down_revision = '019_email_integration'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Structured data from Crunchbase/MAGNiTT (funding amounts, investors, etc.)
    op.add_column('hidden_signals', sa.Column(
        'signal_data', JSONB, nullable=True,
        comment='Structured enrichment: funding_amount, investors, person_name, etc.',
    ))
    # Evidence tier: strong (verified API data) | medium | weak | speculative
    op.add_column('hidden_signals', sa.Column(
        'evidence_tier', sa.String(20), nullable=True, server_default='medium',
        comment='Signal evidence quality: strong | medium | weak | speculative',
    ))
    # Data source provider
    op.add_column('hidden_signals', sa.Column(
        'provider', sa.String(50), nullable=True,
        comment='Data provider: crunchbase | magnitt | serper | adzuna',
    ))


def downgrade() -> None:
    op.drop_column('hidden_signals', 'provider')
    op.drop_column('hidden_signals', 'evidence_tier')
    op.drop_column('hidden_signals', 'signal_data')
