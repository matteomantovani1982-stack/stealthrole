"""Add scout_results table for persistent signal caching

Revision ID: 011
Revises: 010
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '011_scout_results'
down_revision = '010_role_company_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'scout_results',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.String(), nullable=False, index=True),

        # Cached response
        sa.Column('opportunities', JSONB, nullable=False, server_default='[]'),
        sa.Column('live_openings', JSONB, nullable=False, server_default='[]'),
        sa.Column('signals_detected', sa.Integer(), server_default='0'),
        sa.Column('sources_searched', sa.Integer(), server_default='0'),
        sa.Column('scored_by', sa.String(), server_default="''"),

        # Search parameters
        sa.Column('regions', JSONB, server_default='[]'),
        sa.Column('roles', JSONB, server_default='[]'),
        sa.Column('sectors', JSONB, server_default='[]'),

        # Validity
        sa.Column('is_stale', sa.Boolean(), server_default='false'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_scout_results_user_id_created', 'scout_results', ['user_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_scout_results_user_id_created')
    op.drop_table('scout_results')
