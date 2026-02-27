"""Add public profile fields to users table.

Revision ID: 20260227_add_public_profile_fields
Revises: 20260227_add_users_bio
Create Date: 2026-02-27 14:10:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260227_add_public_profile_fields"
down_revision = "20260227_add_users_bio"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        return

    columns = {column["name"] for column in inspector.get_columns("users")}

    if "profile_image_path" not in columns:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(sa.Column("profile_image_path", sa.String(length=255), nullable=True))

    if "experiences" not in columns:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(sa.Column("experiences", sa.JSON(), nullable=False, server_default="[]"))
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.alter_column("experiences", server_default=None)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        return

    columns = {column["name"] for column in inspector.get_columns("users")}

    if "experiences" in columns:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.drop_column("experiences")

    if "profile_image_path" in columns:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.drop_column("profile_image_path")
