"""Add location column to candidate_profiles and migrate from global_context JSON

Revision ID: 032_candidate_location
Revises: 031_linkedin_messages
Create Date: 2026-04-30

Fixes data modeling: location was previously buried in global_context JSON text field.
This migration:
  1. Adds a proper location column (String(255), nullable)
  2. Migrates existing location data from global_context JSON to the new column
  3. Provides clean downgrade path
"""
from alembic import op
import sqlalchemy as sa

revision = '032_candidate_location'
down_revision = '031_linkedin_messages'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add the new location column
    op.add_column(
        'candidate_profiles',
        sa.Column(
            'location',
            sa.String(255),
            nullable=True,
            comment="Candidate preferred location / region",
        ),
    )

    # Migrate existing location data from global_context JSON to the new column.
    # global_context is a free-form Text column — historically some rows held plain
    # English ("I'm pivoting from founder to corporate"), others hold JSON
    # ({"location":"Dubai",...}). A blanket ::jsonb cast crashes on the first
    # non-JSON row. Loop in Python and skip rows that don't parse.
    import json as _json
    from sqlalchemy import text as _text

    conn = op.get_bind()
    rows = conn.execute(
        _text("SELECT id, global_context FROM candidate_profiles WHERE global_context IS NOT NULL")
    ).fetchall()

    for row in rows:
        try:
            ctx = _json.loads(row.global_context)
        except (ValueError, TypeError):
            continue
        if not isinstance(ctx, dict):
            continue
        loc = (ctx.get("location") or "")
        if isinstance(loc, str):
            loc = loc.strip()
        if not loc:
            continue
        conn.execute(
            _text("UPDATE candidate_profiles SET location = :loc WHERE id = :pid"),
            {"loc": loc[:255], "pid": row.id},
        )


def downgrade() -> None:
    op.drop_column('candidate_profiles', 'location')
