"""Add persisted profile_image filename to users table.

Revision ID: 20260227_add_profile_image_filename
Revises: 20260227_backfill_blog_authors
Create Date: 2026-02-27 15:45:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "20260227_add_profile_image_filename"
down_revision = "20260227_backfill_blog_authors"
branch_labels = None
depends_on = None


DEFAULT_PROFILE_IMAGE = "default.png"


def _normalized_filename(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return DEFAULT_PROFILE_IMAGE

    lowered = raw.lower()
    if lowered.startswith("http://") or lowered.startswith("https://"):
        return DEFAULT_PROFILE_IMAGE

    normalized = raw.replace("\\", "/")
    if "/" in normalized:
        normalized = normalized.rsplit("/", 1)[-1]

    return normalized or DEFAULT_PROFILE_IMAGE


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        return

    columns = {column["name"] for column in inspector.get_columns("users")}

    if "profile_image" not in columns:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "profile_image",
                    sa.String(length=255),
                    nullable=False,
                    server_default=DEFAULT_PROFILE_IMAGE,
                )
            )
        columns.add("profile_image")

    if "profile_image_path" in columns:
        rows = bind.execute(text("SELECT id, profile_image_path FROM users")).fetchall()
        for row in rows:
            user_id = int(row[0])
            filename = _normalized_filename(row[1])
            bind.execute(
                text("UPDATE users SET profile_image = :filename WHERE id = :user_id"),
                {"filename": filename, "user_id": user_id},
            )

    bind.execute(
        text(
            """
            UPDATE users
            SET profile_image = :default_image
            WHERE profile_image IS NULL OR trim(profile_image) = ''
            """
        ),
        {"default_image": DEFAULT_PROFILE_IMAGE},
    )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "profile_image",
            existing_type=sa.String(length=255),
            nullable=False,
            server_default=DEFAULT_PROFILE_IMAGE,
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "profile_image" in columns:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.drop_column("profile_image")
