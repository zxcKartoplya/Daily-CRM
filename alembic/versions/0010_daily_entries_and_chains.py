"""replace daily reports with daily entries and work chains

Revision ID: 0010_daily_entries_and_chains
Revises: 0009_work_schedule
"""
from alembic import op
import sqlalchemy as sa


revision = "0010_daily_entries_and_chains"
down_revision = "0009_work_schedule"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("internal_chat_messages", schema=None) as batch_op:
        batch_op.drop_column("daily_report_id")
        batch_op.drop_column("parsed_to_daily_report")

    op.drop_table("daily_report_tasks")
    op.drop_table("daily_reports")

    op.create_table(
        "daily_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("day_type", sa.String(), nullable=False, server_default="work"),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "date", name="uq_daily_entries_user_date"),
    )
    op.create_index("ix_daily_entries_id", "daily_entries", ["id"])
    op.create_index("ix_daily_entries_user_id", "daily_entries", ["user_id"])
    op.create_index("ix_daily_entries_department_id", "daily_entries", ["department_id"])
    op.create_index("ix_daily_entries_date", "daily_entries", ["date"])
    op.create_index("ix_daily_entries_user_id_date", "daily_entries", ["user_id", "date"])

    op.create_table(
        "entry_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.Column("chain_id", sa.String(length=36), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("link", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["entry_id"], ["daily_entries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chain_id", "entry_id", name="uq_entry_items_chain_id_entry_id"),
    )
    op.create_index("ix_entry_items_id", "entry_items", ["id"])
    op.create_index("ix_entry_items_entry_id", "entry_items", ["entry_id"])
    op.create_index("ix_entry_items_chain_id", "entry_items", ["chain_id"])
    op.create_index("ix_entry_items_status", "entry_items", ["status"])


def downgrade() -> None:
    op.drop_table("entry_items")
    op.drop_table("daily_entries")

    op.create_table(
        "daily_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("blockers_text", sa.Text(), nullable=True),
        sa.Column("blocker_type", sa.String(), nullable=True),
        sa.Column("self_rating", sa.Integer(), nullable=True),
        sa.Column("needs_help", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "report_date", name="uq_daily_reports_user_report_date"),
    )
    op.create_index("ix_daily_reports_user_id", "daily_reports", ["user_id"])
    op.create_index("ix_daily_reports_department_id", "daily_reports", ["department_id"])
    op.create_index("ix_daily_reports_report_date", "daily_reports", ["report_date"])

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

    with op.batch_alter_table("internal_chat_messages", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("parsed_to_daily_report", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("daily_report_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_internal_chat_messages_daily_report_id",
            "daily_reports",
            ["daily_report_id"],
            ["id"],
            ondelete="SET NULL",
        )
