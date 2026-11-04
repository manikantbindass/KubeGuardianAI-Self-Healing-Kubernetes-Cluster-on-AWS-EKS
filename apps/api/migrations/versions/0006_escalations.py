"""Durable, deduplicated escalation delivery and retry state."""

import sqlalchemy as sa
from alembic import op

revision = "0006_escalations"
down_revision = "0005_queue_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "escalation_deliveries",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("namespace", sa.String(63), nullable=False),
        sa.Column("destination", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.Integer(), nullable=True),
    )
    op.create_index("ix_escalation_due", "escalation_deliveries", ["state", "next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_escalation_due", table_name="escalation_deliveries")
    op.drop_table("escalation_deliveries")
