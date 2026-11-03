"""Durable advisory anomaly evidence attached to an incident."""

import sqlalchemy as sa
from alembic import op

revision = "0003_anomaly_evidence"
down_revision = "0002_incidents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "anomaly_evidence",
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id"), primary_key=True),
        sa.Column("detector", sa.String(32), nullable=False),
        sa.Column("model_version", sa.String(128), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("threshold", sa.Float, nullable=False),
        sa.Column("provenance", sa.String(16), nullable=False),
        sa.Column("explanations", sa.JSON, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("anomaly_evidence")
