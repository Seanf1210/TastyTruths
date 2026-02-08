"""Add nutrition_per_100g to ingredients

Revision ID: 1b2c3d4e5f6a
Revises: d3f4b1c2a9e8
Create Date: 2026-02-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1b2c3d4e5f6a"
down_revision = "d3f4b1c2a9e8"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("ingredients", schema=None) as batch_op:
        batch_op.add_column(sa.Column("nutrition_per_100g", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("ingredients", schema=None) as batch_op:
        batch_op.drop_column("nutrition_per_100g")
