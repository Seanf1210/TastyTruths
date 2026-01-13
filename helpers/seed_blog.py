#!/usr/bin/env python
"""
Seed script to populate the database with example blog posts.
Run with: python helpers/seed_blog.py
"""

import os

from app import create_app
from services.db import db
from services.models import BlogPost, User


def seed_blog_posts():
    """Create and insert two example blog posts."""
    app = create_app()

    with app.app_context():
        existing = {p.title for p in BlogPost.query.all()}
        username = os.environ.get("SEED_BLOG_USERNAME", "").strip()
        user = None
        if username:
            user = User.query.filter_by(username=username).first()
        if not user:
            user = User.query.order_by(User.id.asc()).first()
        if not user:
            print("No users found. Create a user first, then re-run this script.")
            return

        posts = [
            BlogPost(
                user_id=user.id,
                title="Why We Test Every Recipe Twice",
                summary="A quick look at how our kitchen process keeps recipes reliable and repeatable.",
                content=(
                    "We want every recipe to work the first time you try it.\n\n"
                    "That is why we cook every dish at least twice, on different days, and "
                    "with slightly different equipment. The goal is consistency, not perfection, "
                    "so we note every adjustment that makes a recipe more dependable.\n\n"
                    "When you see a Tasty Truths recipe, you can trust that the steps have been "
                    "written from real experience in the kitchen."
                ),
            ),
            BlogPost(
                user_id=user.id,
                title="Stocking a Calm, Efficient Pantry",
                summary="Simple pantry staples that help you cook faster without sacrificing flavor.",
                content=(
                    "A calm pantry makes weeknight cooking feel easier. Start with versatile "
                    "basics like grains, beans, vinegars, and a few reliable spices.\n\n"
                    "We also keep a short list of quick upgrades on hand: good olive oil, canned "
                    "tomatoes, and a few frozen vegetables. These let you build real flavor fast.\n\n"
                    "The goal is not to buy everything at once. Add one or two essentials each "
                    "week and let the pantry grow with your cooking style."
                ),
            ),
        ]

        created = []
        for post in posts:
            if post.title in existing:
                continue
            db.session.add(post)
            created.append(post.title)

        if not created:
            print("No new blog posts added. Sample posts already exist.")
            return

        try:
            db.session.commit()
            print(f"Seeded blog posts for {user.username}:")
            for title in created:
                print(f"- {title}")
        except Exception as exc:
            db.session.rollback()
            print(f"Error seeding blog posts: {exc}")
            raise


if __name__ == "__main__":
    seed_blog_posts()
