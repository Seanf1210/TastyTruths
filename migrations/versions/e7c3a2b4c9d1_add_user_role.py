"""add user role column

Revision ID: e7c3a2b4c9d1
Revises: a9f1d7c4e2b0
Create Date: 2026-02-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e7c3a2b4c9d1"
down_revision = "a9f1d7c4e2b0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "role",
                sa.String(length=20),
                nullable=False,
                server_default="normal",
            )
        )


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("role")
