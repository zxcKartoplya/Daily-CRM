"""store ai assessments history

Revision ID: 0011_ai_assessments
Revises: 0010_daily_entries_and_chains
"""
from alembic import op
import sqlalchemy as sa


revision = "0011_ai_assessments"
down_revision = "0010_daily_entries_and_chains"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assessments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=True),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("period_from", sa.Date(), nullable=False),
        sa.Column("period_to", sa.Date(), nullable=False),
        sa.Column("feedback_text", sa.Text(), nullable=False),
        sa.Column("metrics_snapshot", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["worker_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["reviewers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assessments_id", "assessments", ["id"])
    op.create_index("ix_assessments_worker_id", "assessments", ["worker_id"])
    op.create_index("ix_assessments_reviewer_id", "assessments", ["reviewer_id"])
    op.create_index("ix_assessments_created_at", "assessments", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_assessments_created_at", table_name="assessments")
    op.drop_index("ix_assessments_reviewer_id", table_name="assessments")
    op.drop_index("ix_assessments_worker_id", table_name="assessments")
    op.drop_index("ix_assessments_id", table_name="assessments")
    op.drop_table("assessments")
