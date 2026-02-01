"""Add metrics to reviewers."""

from alembic import op
import sqlalchemy as sa


revision = "0003_add_reviewer_metrics"
down_revision = "0002_add_admins"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reviewers", sa.Column("metrics", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("reviewers", "metrics")
