"""edited_at on daily entries

Revision ID: 0012_daily_entry_edited_at
Revises: 0011_ai_assessments
"""
from alembic import op
import sqlalchemy as sa


revision = "0012_daily_entry_edited_at"
down_revision = "0011_ai_assessments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("daily_entries", schema=None) as batch_op:
        batch_op.add_column(sa.Column("edited_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("daily_entries", schema=None) as batch_op:
        batch_op.drop_column("edited_at")
