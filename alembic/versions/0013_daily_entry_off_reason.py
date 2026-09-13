"""off reason on daily entries

Revision ID: 0013_daily_entry_off_reason
Revises: 0012_daily_entry_edited_at
"""
from alembic import op
import sqlalchemy as sa


revision = "0013_daily_entry_off_reason"
down_revision = "0012_daily_entry_edited_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("daily_entries", schema=None) as batch_op:
        batch_op.add_column(sa.Column("off_reason", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("off_reason_note", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("daily_entries", schema=None) as batch_op:
        batch_op.drop_column("off_reason_note")
        batch_op.drop_column("off_reason")
