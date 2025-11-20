"""Add admins table and link departments."""

from alembic import op
import sqlalchemy as sa


revision = "0002_add_admins"
down_revision = "0001_init_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.UniqueConstraint("email", name="uq_admins_email"),
    )

    with op.batch_alter_table("departments", schema=None) as batch_op:
        batch_op.add_column(sa.Column("admin_id", sa.Integer(), nullable=False))
        batch_op.create_foreign_key(
            "fk_departments_admin_id_admins",
            "admins",
            ["admin_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table("departments", schema=None) as batch_op:
        batch_op.drop_constraint("fk_departments_admin_id_admins", type_="foreignkey")
        batch_op.drop_column("admin_id")

    op.drop_table("admins")

