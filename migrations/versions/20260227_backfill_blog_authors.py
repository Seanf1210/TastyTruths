"""Backfill and enforce blog author foreign key.

Revision ID: 20260227_backfill_blog_authors
Revises: 20260227_add_public_profile_fields
Create Date: 2026-02-27 15:05:00
"""

from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "20260227_backfill_blog_authors"
down_revision = "20260227_add_public_profile_fields"
branch_labels = None
depends_on = None


def _get_or_create_fallback_user_id(bind, inspector):
    row = bind.execute(
        text("SELECT id FROM users WHERE lower(username) = 'demo_user' LIMIT 1")
    ).fetchone()
    if row:
        return int(row[0])

    row = bind.execute(text("SELECT id FROM users ORDER BY id ASC LIMIT 1")).fetchone()
    if row:
        return int(row[0])

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    created_at = datetime.utcnow().isoformat(sep=" ")
    values = {
        "username": "demo_user",
        "password_hash": "migration-placeholder-hash",
        "role": "normal",
    }
    if "bio" in user_columns:
        values["bio"] = ""
    if "dietary_restrictions" in user_columns:
        values["dietary_restrictions"] = "[]"
    if "experiences" in user_columns:
        values["experiences"] = "[]"
    if "profile_image" in user_columns:
        values["profile_image"] = "default.png"
    if "created_at" in user_columns:
        values["created_at"] = created_at

    columns = ", ".join(values.keys())
    placeholders = ", ".join(f":{key}" for key in values.keys())
    bind.execute(
        text(f"INSERT INTO users ({columns}) VALUES ({placeholders})"),
        values,
    )
    row = bind.execute(
        text("SELECT id FROM users WHERE lower(username) = 'demo_user' LIMIT 1")
    ).fetchone()
    return int(row[0]) if row else None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("users") or not inspector.has_table("blog_posts"):
        return

    blog_columns = {column["name"] for column in inspector.get_columns("blog_posts")}
    if "user_id" not in blog_columns:
        with op.batch_alter_table("blog_posts", schema=None) as batch_op:
            batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        blog_columns.add("user_id")

    fallback_user_id = _get_or_create_fallback_user_id(bind, inspector)
    if fallback_user_id is None:
        return

    # Backfill null and orphaned rows to a valid user.
    bind.execute(
        text("UPDATE blog_posts SET user_id = :uid WHERE user_id IS NULL"),
        {"uid": fallback_user_id},
    )
    bind.execute(
        text(
            """
            UPDATE blog_posts
            SET user_id = :uid
            WHERE user_id IS NOT NULL
              AND user_id NOT IN (SELECT id FROM users)
            """
        ),
        {"uid": fallback_user_id},
    )

    indexes = {index["name"] for index in inspector.get_indexes("blog_posts")}
    foreign_keys = inspector.get_foreign_keys("blog_posts")
    has_user_fk = any(
        fk.get("referred_table") == "users"
        and fk.get("constrained_columns") == ["user_id"]
        for fk in foreign_keys
    )

    # Keep NO ACTION behavior to match existing delete flows.
    with op.batch_alter_table("blog_posts", schema=None) as batch_op:
        if not has_user_fk:
            batch_op.create_foreign_key(
                "fk_blog_posts_user_id_users",
                "users",
                ["user_id"],
                ["id"],
            )
        if "ix_blog_posts_user_id" not in indexes:
            batch_op.create_index("ix_blog_posts_user_id", ["user_id"], unique=False)
        batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("blog_posts"):
        return

    indexes = {index["name"] for index in inspector.get_indexes("blog_posts")}
    foreign_keys = inspector.get_foreign_keys("blog_posts")
    fk_names = [
        fk.get("name")
        for fk in foreign_keys
        if fk.get("referred_table") == "users"
        and fk.get("constrained_columns") == ["user_id"]
    ]

    with op.batch_alter_table("blog_posts", schema=None) as batch_op:
        for fk_name in fk_names:
            if fk_name:
                batch_op.drop_constraint(fk_name, type_="foreignkey")
        if "ix_blog_posts_user_id" in indexes:
            batch_op.drop_index("ix_blog_posts_user_id")
        batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=True)
