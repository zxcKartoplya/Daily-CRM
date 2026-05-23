"""remove admins table and department admin_id

Revision ID: 0007_remove_admins
Revises: 0006_job_reviewer_required
Create Date: 2026-05-23

"""
from alembic import op
import sqlalchemy as sa

revision = "0007_remove_admins"
down_revision = "0006_job_reviewer_required"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("departments", schema=None) as batch_op:
        batch_op.drop_constraint("fk_departments_admin_id_admins", type_="foreignkey")
        batch_op.drop_column("admin_id")

    op.drop_table("admins")


def downgrade() -> None:
    op.create_table(
        "admins",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_admins_email"),
    )

    with op.batch_alter_table("departments", schema=None) as batch_op:
        batch_op.add_column(sa.Column("admin_id", sa.Integer(), nullable=True))
