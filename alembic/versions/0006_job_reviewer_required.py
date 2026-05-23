"""job reviewer required

Revision ID: 0006_job_reviewer_required
Revises: 0005_refactor_employee_domain
Create Date: 2026-05-23

"""
from alembic import op
import sqlalchemy as sa

revision = "0006_job_reviewer_required"
down_revision = "0005_refactor_employee_domain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.alter_column("reviewer_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.alter_column("reviewer_id", existing_type=sa.Integer(), nullable=True)
