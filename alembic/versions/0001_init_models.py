"""Initial models for Daily CRM."""

from alembic import op
import sqlalchemy as sa


revision = "0001_init_models"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.UniqueConstraint("name", name="uq_departments_name"),
    )

    op.create_table(
        "reviewers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name="fk_jobs_department_id_departments",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"],
            ["reviewers.id"],
            name="fk_jobs_reviewer_id_reviewers",
            ondelete="SET NULL",
        ),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name="fk_users_job_id_jobs",
            ondelete="RESTRICT",
        ),
    )

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


def downgrade() -> None:
    op.drop_table("statistics")
    op.drop_table("tasks")
    op.drop_table("users")
    op.drop_table("jobs")
    op.drop_table("reviewers")
    op.drop_table("departments")
