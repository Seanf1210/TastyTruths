"""Normalize friendships to canonical pair storage.

Revision ID: 20260306_normalize_friendships_canonical
Revises: 20260305_add_friendships
Create Date: 2026-03-06 10:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260306_normalize_friendships_canonical"
down_revision = "20260305_add_friendships"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("friendships"):
        return

    bind.execute(
        sa.text(
            """
            UPDATE friendships
            SET user_id = CASE WHEN user_id < friend_id THEN user_id ELSE friend_id END,
                friend_id = CASE WHEN user_id < friend_id THEN friend_id ELSE user_id END
            """
        )
    )
    bind.execute(
        sa.text(
            """
            DELETE FROM friendships
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM friendships
                GROUP BY user_id, friend_id
            )
            """
        )
    )

    with op.batch_alter_table("friendships", schema=None) as batch_op:
        batch_op.create_check_constraint(
            "ck_friendships_canonical_order",
            "user_id < friend_id",
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("friendships"):
        return

    with op.batch_alter_table("friendships", schema=None) as batch_op:
        batch_op.drop_constraint("ck_friendships_canonical_order", type_="check")
