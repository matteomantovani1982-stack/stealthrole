"""Create warm_intros table for Relationship Engine

Revision ID: 023_relationship_engine
Revises: 022_linkedin_integration
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '023_relationship_engine'
down_revision = '022_linkedin_integration'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'warm_intros',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', sa.String(255), nullable=False, index=True),
        sa.Column('connection_id', UUID(as_uuid=True), sa.ForeignKey('linkedin_connections.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('application_id', UUID(as_uuid=True), sa.ForeignKey('applications.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('target_company', sa.String(255), nullable=False),
        sa.Column('target_role', sa.String(255), nullable=True),
        sa.Column('target_person', sa.String(255), nullable=True),
        sa.Column('status', sa.String(30), nullable=False, server_default='identified', index=True),
        sa.Column('outreach_message', sa.Text, nullable=True),
        sa.Column('response_message', sa.Text, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('relationship_context', sa.String(500), nullable=True),
        sa.Column('intro_angle', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # One intro request per connection per application
    op.create_index('ix_warm_intros_conn_app', 'warm_intros', ['connection_id', 'application_id'], unique=True)
    # Pipeline queries
    op.create_index('ix_warm_intros_user_status', 'warm_intros', ['user_id', 'status'])


def downgrade() -> None:
    op.drop_index('ix_warm_intros_user_status', table_name='warm_intros')
    op.drop_index('ix_warm_intros_conn_app', table_name='warm_intros')
    op.drop_table('warm_intros')
