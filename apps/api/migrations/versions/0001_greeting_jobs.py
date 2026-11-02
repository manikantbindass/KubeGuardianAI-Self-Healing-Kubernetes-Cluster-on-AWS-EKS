"""Create durable greeting jobs."""

import sqlalchemy as sa
from alembic import op

revision = "0001_greeting_jobs"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "greeting_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("message", sa.String(160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_greeting_jobs_status", "greeting_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_greeting_jobs_status", table_name="greeting_jobs")
    op.drop_table("greeting_jobs")
