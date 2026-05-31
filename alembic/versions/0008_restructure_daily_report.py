"""restructure daily report: remove text fields, add blocker_type, add daily_report_tasks table

Revision ID: 0008_restructure_daily_report
Revises: 0007_remove_admins
Create Date: 2026-05-30

"""
from alembic import op
import sqlalchemy as sa

revision = "0008_restructure_daily_report"
down_revision = "0007_remove_admins"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_report_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("task_text", sa.String(), nullable=True),
        sa.Column("slot", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["daily_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_daily_report_tasks_id", "daily_report_tasks", ["id"])
    op.create_index("ix_daily_report_tasks_report_id", "daily_report_tasks", ["report_id"])

    with op.batch_alter_table("daily_reports", schema=None) as batch_op:
        batch_op.drop_column("yesterday_text")
        batch_op.drop_column("today_text")
        batch_op.drop_column("mood")
        batch_op.add_column(sa.Column("blocker_type", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("daily_reports", schema=None) as batch_op:
        batch_op.drop_column("blocker_type")
        batch_op.add_column(sa.Column("mood", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("today_text", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("yesterday_text", sa.Text(), nullable=True))

    op.drop_index("ix_daily_report_tasks_report_id", table_name="daily_report_tasks")
    op.drop_index("ix_daily_report_tasks_id", table_name="daily_report_tasks")
    op.drop_table("daily_report_tasks")
