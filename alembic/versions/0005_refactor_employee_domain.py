"""Refactor backend around employee daily reports and RBAC users."""

from alembic import op
import sqlalchemy as sa


revision = "0005_refactor_employee_domain"
down_revision = "0004_add_job_description"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("departments", schema=None) as batch_op:
        batch_op.alter_column("admin_id", existing_type=sa.Integer(), nullable=True)

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("job_id", existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column("email", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("password_hash", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("role", sa.String(), nullable=False, server_default="employee"))
        batch_op.add_column(sa.Column("department_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("status", sa.String(), nullable=False, server_default="active"))
        batch_op.add_column(
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))
        )
        batch_op.add_column(
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))
        )
        batch_op.create_foreign_key(
            "fk_users_department_id_departments",
            "departments",
            ["department_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_unique_constraint("uq_users_email", ["email"])
        batch_op.create_index("ix_users_department_id", ["department_id"], unique=False)

    op.execute(
        """
        UPDATE users
        SET department_id = (
            SELECT jobs.department_id
            FROM jobs
            WHERE jobs.id = users.job_id
        )
        WHERE job_id IS NOT NULL
        """
    )

    op.execute(
        """
        INSERT INTO users (name, email, password_hash, role, status, created_at, updated_at)
        SELECT admins.full_name, admins.email, admins.password_hash, 'admin', 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM admins
        WHERE NOT EXISTS (
            SELECT 1
            FROM users
            WHERE users.email = admins.email
        )
        """
    )

    op.create_table(
        "employee_profiles",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.String(), nullable=True),
        sa.Column("avatar", sa.String(), nullable=True),
        sa.Column("timezone", sa.String(), nullable=True),
        sa.Column("preferred_language", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "employee_settings",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("notification_time", sa.Time(), nullable=True),
        sa.Column("reminder_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("daily_template_id", sa.String(), nullable=True),
        sa.Column("preferred_daily_format", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "daily_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(), nullable=False, server_default="internal_web"),
        sa.Column("status", sa.String(), nullable=False, server_default="submitted"),
        sa.Column("submitted_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("yesterday_text", sa.Text(), nullable=True),
        sa.Column("today_text", sa.Text(), nullable=True),
        sa.Column("blockers_text", sa.Text(), nullable=True),
        sa.Column("mood", sa.String(), nullable=True),
        sa.Column("self_rating", sa.Integer(), nullable=True),
        sa.Column("needs_help", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", "report_date", name="uq_daily_reports_user_report_date"),
    )
    op.create_index("ix_daily_reports_user_id", "daily_reports", ["user_id"])
    op.create_index("ix_daily_reports_department_id", "daily_reports", ["department_id"])
    op.create_index("ix_daily_reports_report_date", "daily_reports", ["report_date"])

    op.create_table(
        "internal_chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("parsed_to_daily_report", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("daily_report_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["daily_report_id"], ["daily_reports.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_internal_chat_messages_user_id", "internal_chat_messages", ["user_id"])

    op.execute(
        """
        INSERT INTO employee_profiles (user_id, position)
        SELECT users.id, jobs.name
        FROM users
        LEFT JOIN jobs ON jobs.id = users.job_id
        WHERE users.role = 'employee'
        """
    )
    op.execute(
        """
        INSERT INTO employee_settings (user_id, reminder_enabled)
        SELECT users.id, 1
        FROM users
        WHERE users.role = 'employee'
        """
    )


def downgrade() -> None:
    op.drop_index("ix_internal_chat_messages_user_id", table_name="internal_chat_messages")
    op.drop_table("internal_chat_messages")

    op.drop_index("ix_daily_reports_report_date", table_name="daily_reports")
    op.drop_index("ix_daily_reports_department_id", table_name="daily_reports")
    op.drop_index("ix_daily_reports_user_id", table_name="daily_reports")
    op.drop_table("daily_reports")

    op.drop_table("employee_settings")
    op.drop_table("employee_profiles")

    op.execute("DELETE FROM users WHERE job_id IS NULL")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index("ix_users_department_id")
        batch_op.drop_constraint("fk_users_department_id_departments", type_="foreignkey")
        batch_op.drop_constraint("uq_users_email", type_="unique")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("created_at")
        batch_op.drop_column("status")
        batch_op.drop_column("department_id")
        batch_op.drop_column("role")
        batch_op.drop_column("password_hash")
        batch_op.drop_column("email")
        batch_op.alter_column("job_id", existing_type=sa.Integer(), nullable=False)

    op.execute(
        """
        UPDATE departments
        SET admin_id = (
            SELECT admins.id
            FROM admins
            ORDER BY admins.id
            LIMIT 1
        )
        WHERE admin_id IS NULL
        """
    )
    with op.batch_alter_table("departments", schema=None) as batch_op:
        batch_op.alter_column("admin_id", existing_type=sa.Integer(), nullable=False)
