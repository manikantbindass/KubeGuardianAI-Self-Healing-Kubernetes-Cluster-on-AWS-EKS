"""Persistent normalized telemetry incidents."""

import sqlalchemy as sa
from alembic import op

revision = "0002_incidents"
down_revision = "0001_greeting_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False, unique=True),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("namespace", sa.String(63), nullable=False),
        sa.Column("resource", sa.String(253), nullable=False),
        sa.Column("reason", sa.String(128), nullable=False),
        sa.Column("summary", sa.String(1024), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("occurrences", sa.Integer, nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_incidents_source", "incidents", ["source"])
    op.create_index("ix_incidents_status", "incidents", ["status"])


def downgrade() -> None:
    op.drop_table("incidents")
