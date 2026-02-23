"""Add dietary_restrictions to users

Revision ID: a9f1d7c4e2b0
Revises: 1b2c3d4e5f6a
Create Date: 2026-02-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a9f1d7c4e2b0"
down_revision = "1b2c3d4e5f6a"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "dietary_restrictions",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("dietary_restrictions")
