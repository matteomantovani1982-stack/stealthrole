"""Add signal intelligence layer tables and columns

Signal Interpretation + Quality Filter + Global Propagation data layer.

New tables:
  - signal_interpretations: structured business analysis of market signals
  - propagation_adjustments: global cross-user learning adjustments

Extended tables:
  - hidden_signals: quality scoring columns + prediction tracking
  - user_intelligence: hybrid learning profile + short-term memory

Revision ID: 033_signal_intelligence_layer
Revises: 032_candidate_location
Create Date: 2026-05-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "033_signal_intelligence_layer"
down_revision = "032_candidate_location"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── New table: signal_interpretations ─────────────────────────────────
    op.create_table(
        "signal_interpretations",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("signal_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("user_id", sa.String(255), nullable=False, index=True),
        # Rule provenance
        sa.Column("rule_id", sa.String(50), nullable=False, index=True),
        sa.Column("rule_version", sa.Integer, nullable=False, server_default="1"),
        # Signal classification
        sa.Column("trigger_type", sa.String(50), nullable=False),
        sa.Column("trigger_subtype", sa.String(50), nullable=True),
        # Interpretation output
        sa.Column("business_change", sa.Text, nullable=False),
        sa.Column("org_impact", sa.Text, nullable=False),
        sa.Column("hiring_reason", sa.Text, nullable=False),
        sa.Column("predicted_roles", JSONB, nullable=False, server_default="[]"),
        # Hiring owner
        sa.Column("hiring_owner_title", sa.String(255), nullable=True),
        sa.Column("hiring_owner_dept", sa.String(50), nullable=True),
        # Scores
        sa.Column("quality_score", sa.Float, nullable=True),
        sa.Column("interpretation_confidence", sa.Float, nullable=True),
        # Timestamps
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()")
        ),
    )

    # ── New table: propagation_adjustments ────────────────────────────────
    op.create_table(
        "propagation_adjustments",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()")
        ),
        # Target
        sa.Column("dimension", sa.String(30), nullable=False, index=True),
        sa.Column("target_key", sa.String(255), nullable=False, index=True),
        # Adjustment
        sa.Column("adjustment_type", sa.String(20), nullable=False),
        sa.Column("adjustment_value", sa.Float, nullable=False),
        sa.Column("previous_value", sa.Float, nullable=True),
        # Evidence
        sa.Column("activation_metric", sa.Text, nullable=True),
        sa.Column("distinct_users", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_outcomes", sa.Integer, nullable=False, server_default="0"),
        # Rollout
        sa.Column("rollout_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rollout_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rollout_progress", sa.Float, nullable=False, server_default="0.0"),
        # Lifecycle
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversal_reason", sa.Text, nullable=True),
        # Timestamps
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()")
        ),
    )
    op.create_index(
        "ix_propagation_dim_target",
        "propagation_adjustments",
        ["dimension", "target_key"],
    )

    # ── Extend hidden_signals: quality scoring columns ───────────────────
    with op.batch_alter_table("hidden_signals") as batch_op:
        batch_op.add_column(sa.Column("quality_score", sa.Float, nullable=True))
        batch_op.add_column(sa.Column("quality_confidence", sa.Float, nullable=True))
        batch_op.add_column(sa.Column("quality_recency", sa.Float, nullable=True))
        batch_op.add_column(
            sa.Column("quality_relevance", sa.Float, nullable=True)
        )
        batch_op.add_column(
            sa.Column("quality_historical", sa.Float, nullable=True)
        )
        batch_op.add_column(
            sa.Column("quality_gate_result", sa.String(20), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "quality_computed_at", sa.DateTime(timezone=True),
                nullable=True
            )
        )
        # Prediction tracking
        batch_op.add_column(
            sa.Column("prediction_id", UUID(as_uuid=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "outcome_tracked", sa.Boolean, nullable=False,
                server_default="false"
            )
        )
        batch_op.add_column(sa.Column("outcome_result", sa.String(20), nullable=True))

    # ── Extend user_intelligence: learning profile columns ───────────────
    with op.batch_alter_table("user_intelligence") as batch_op:
        batch_op.add_column(
            sa.Column("learning_profile", JSONB, nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "learning_sample_count", sa.Integer, nullable=False,
                server_default="0"
            )
        )
        batch_op.add_column(
            sa.Column(
                "learning_updated_at", sa.DateTime(timezone=True),
                nullable=True
            )
        )
        batch_op.add_column(
            sa.Column("short_term_memory", JSONB, nullable=True)
        )


def downgrade() -> None:
    # ── Remove user_intelligence extensions ───────────────────────────────
    with op.batch_alter_table("user_intelligence") as batch_op:
        batch_op.drop_column("short_term_memory")
        batch_op.drop_column("learning_updated_at")
        batch_op.drop_column("learning_sample_count")
        batch_op.drop_column("learning_profile")

    # ── Remove hidden_signals extensions ──────────────────────────────────
    with op.batch_alter_table("hidden_signals") as batch_op:
        batch_op.drop_column("outcome_result")
        batch_op.drop_column("outcome_tracked")
        batch_op.drop_column("prediction_id")
        batch_op.drop_column("quality_computed_at")
        batch_op.drop_column("quality_gate_result")
        batch_op.drop_column("quality_historical")
        batch_op.drop_column("quality_relevance")
        batch_op.drop_column("quality_recency")
        batch_op.drop_column("quality_confidence")
        batch_op.drop_column("quality_score")

    # ── Drop new tables ──────────────────────────────────────────────────
    op.drop_table("propagation_adjustments")
    op.drop_table("signal_interpretations")
