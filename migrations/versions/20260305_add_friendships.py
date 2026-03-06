"""Add friend requests and friendships tables.

Revision ID: 20260305_add_friendships
Revises: 20260301_add_users_experience
Create Date: 2026-03-05 12:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260305_add_friendships"
down_revision = "20260301_add_users_experience"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("friend_requests"):
        op.create_table(
            "friend_requests",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("requester_id", sa.Integer(), nullable=False),
            sa.Column("recipient_id", sa.Integer(), nullable=False),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default="pending",
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.CheckConstraint("requester_id <> recipient_id", name="ck_friend_requests_not_self"),
            sa.CheckConstraint(
                "status IN ('pending', 'accepted', 'declined', 'canceled')",
                name="ck_friend_requests_status",
            ),
            sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["requester_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_friend_requests_requester_id",
            "friend_requests",
            ["requester_id"],
            unique=False,
        )
        op.create_index(
            "ix_friend_requests_recipient_id",
            "friend_requests",
            ["recipient_id"],
            unique=False,
        )
        op.create_index(
            "ix_friend_requests_status",
            "friend_requests",
            ["status"],
            unique=False,
        )

    if not inspector.has_table("friendships"):
        op.create_table(
            "friendships",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("friend_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.CheckConstraint("user_id <> friend_id", name="ck_friendships_not_self"),
            sa.ForeignKeyConstraint(["friend_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "friend_id", name="uq_friendships_user_friend"),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("friendships"):
        op.drop_table("friendships")

    if inspector.has_table("friend_requests"):
        op.drop_index("ix_friend_requests_status", table_name="friend_requests")
        op.drop_index("ix_friend_requests_recipient_id", table_name="friend_requests")
        op.drop_index("ix_friend_requests_requester_id", table_name="friend_requests")
        op.drop_table("friend_requests")
