"""work schedule on jobs and users

Revision ID: 0009_work_schedule
Revises: 0008_restructure_daily_report
"""
from alembic import op
import sqlalchemy as sa


revision = "0009_work_schedule"
down_revision = "0008_restructure_daily_report"
branch_labels = None
depends_on = None

DEFAULT_WORK_DAYS = "[1, 2, 3, 4, 5]"


def upgrade() -> None:
    for table in ("jobs", "users"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("schedule_type", sa.String(), nullable=False, server_default="weekly")
            )
            batch_op.add_column(
                sa.Column("work_days", sa.JSON(), nullable=True, server_default=DEFAULT_WORK_DAYS)
            )
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column("schedule_type", server_default=None)
            batch_op.alter_column("work_days", server_default=None)


def downgrade() -> None:
    for table in ("users", "jobs"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("work_days")
            batch_op.drop_column("schedule_type")
