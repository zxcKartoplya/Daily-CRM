"""Add description field to jobs."""

from alembic import op
import sqlalchemy as sa


revision = "0004_add_job_description"
down_revision = "0003_add_reviewer_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("description", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "description")
