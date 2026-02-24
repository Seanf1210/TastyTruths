"""Add ingredient dietary tags tables

Revision ID: d3f4b1c2a9e8
Revises: c81e87f5546b
Create Date: 2026-01-31 18:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d3f4b1c2a9e8"
down_revision = "c81e87f5546b"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "ingredients" not in tables:
        op.create_table(
            "ingredients",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=200), nullable=False),
        )
        op.create_index("ix_ingredients_name", "ingredients", ["name"])

    if "dietary_tags" not in tables:
        op.create_table(
            "dietary_tags",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.UniqueConstraint("name", name="uq_dietary_tags_name"),
        )
        op.create_index("ix_dietary_tags_name", "dietary_tags", ["name"])

    if "ingredient_dietary_tags" not in tables:
        op.create_table(
            "ingredient_dietary_tags",
            sa.Column("ingredient_id", sa.Integer(), nullable=False),
            sa.Column("tag_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["ingredient_id"], ["ingredients.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["tag_id"], ["dietary_tags.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("ingredient_id", "tag_id"),
            sa.UniqueConstraint("ingredient_id", "tag_id", name="uq_ingredient_dietary_tag"),
        )
        op.create_index(
            "ix_ingredient_dietary_tags_tag_id", "ingredient_dietary_tags", ["tag_id"]
        )


def downgrade():
    op.drop_table("ingredient_dietary_tags")
    op.drop_index("ix_dietary_tags_name", table_name="dietary_tags")
    op.drop_table("dietary_tags")
    op.drop_index("ix_ingredients_name", table_name="ingredients")
    op.drop_table("ingredients")
