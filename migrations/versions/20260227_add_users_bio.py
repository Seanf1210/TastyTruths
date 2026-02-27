"""Add bio column to users table.

Revision ID: 20260227_add_users_bio
Revises:
Create Date: 2026-02-27 13:45:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260227_add_users_bio"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "bio" in columns:
        return

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("bio", sa.Text(), nullable=True, server_default=""))

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("bio", server_default=None)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "bio" not in columns:
        return

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("bio")
