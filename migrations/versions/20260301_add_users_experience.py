"""Add experience column to users table.

Revision ID: 20260301_add_users_experience
Revises: 20260227_add_profile_image_filename
Create Date: 2026-03-01 11:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260301_add_users_experience"
down_revision = "20260227_add_profile_image_filename"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "experience" in columns:
        return

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("experience", sa.Text(), nullable=True, server_default=""))

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("experience", server_default=None)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "experience" not in columns:
        return

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("experience")
