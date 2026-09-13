"""last login timestamp on users

Revision ID: 0014_user_last_login_at
Revises: 0013_daily_entry_off_reason
"""
from alembic import op
import sqlalchemy as sa


revision = "0014_user_last_login_at"
down_revision = "0013_daily_entry_off_reason"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("last_login_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("last_login_at")
