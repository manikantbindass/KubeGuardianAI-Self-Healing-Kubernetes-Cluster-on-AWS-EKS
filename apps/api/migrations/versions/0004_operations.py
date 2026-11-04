"""Persistent operations snapshots, decisions, audit, preferences and reviews."""

import sqlalchemy as sa
from alembic import op

revision = "0004_operations"
down_revision = "0003_anomaly_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operations_snapshots",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("namespace", sa.String(63), nullable=False),
        sa.Column("name", sa.String(253), nullable=False),
        sa.Column("uid", sa.String(128), nullable=False),
        sa.Column("resource_version", sa.String(64), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data", sa.JSON, nullable=False),
    )
    for field in ("mode", "kind", "namespace"):
        op.create_index(f"ix_operations_snapshots_{field}", "operations_snapshots", [field])
    op.create_table(
        "operations_audit",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(256), nullable=False),
        sa.Column("verb", sa.String(64), nullable=False),
        sa.Column("target", sa.String(256), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("detail", sa.JSON, nullable=False),
    )
    op.create_index("ix_operations_audit_mode", "operations_audit", ["mode"])
    op.create_table(
        "operations_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("identity", sa.String(64), nullable=False, unique=True),
        sa.Column("payload_digest", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(256), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("namespace", sa.String(63), nullable=False),
        sa.Column("target", sa.String(253), nullable=False),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("result", sa.Text, nullable=True),
    )
    op.create_index("ix_operations_commands_state", "operations_commands", ["state"])
    op.create_table(
        "operations_preferences",
        sa.Column("actor", sa.String(256), primary_key=True),
        sa.Column("data", sa.JSON, nullable=False),
    )
    op.create_table(
        "operations_incident_reviews",
        sa.Column("incident_id", sa.String(36), primary_key=True),
        sa.Column("actor", sa.String(256), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.String(512), nullable=False),
    )


def downgrade() -> None:
    for table in (
        "operations_incident_reviews",
        "operations_preferences",
        "operations_commands",
        "operations_audit",
        "operations_snapshots",
    ):
        op.drop_table(table)
