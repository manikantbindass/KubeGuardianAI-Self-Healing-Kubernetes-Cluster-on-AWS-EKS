"""Index bounded durable queue admission and ordered worker claims."""

from alembic import op

revision = "0005_queue_index"
down_revision = "0004_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_jobs_status_created", "greeting_jobs", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_jobs_status_created", table_name="greeting_jobs")
