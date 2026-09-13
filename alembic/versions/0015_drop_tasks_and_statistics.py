"""drop legacy tasks and statistics tables

Revision ID: 0015_drop_tasks_and_statistics
Revises: 0014_user_last_login_at
"""
from alembic import op
import sqlalchemy as sa


revision = "0015_drop_tasks_and_statistics"
down_revision = "0014_user_last_login_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("statistics")
    op.drop_table("tasks")


def downgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_tasks_user_id_users",
            ondelete="CASCADE",
        ),
    )

    op.create_table(
        "statistics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_statistics_user_id_users",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "date",
            "user_id",
            name="uq_statistics_date_user",
        ),
    )
