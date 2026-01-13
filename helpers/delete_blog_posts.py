#!/usr/bin/env python
"""
Delete all blog posts from the database.
Run with: python helpers/delete_blog_posts.py
"""

from app import create_app
from services.db import db
from services.models import BlogPost


def delete_blog_posts():
    app = create_app()

    with app.app_context():
        count = BlogPost.query.count()
        if count == 0:
            print("No blog posts to delete.")
            return

        BlogPost.query.delete()
        try:
            db.session.commit()
            print(f"Deleted {count} blog post(s).")
        except Exception as exc:
            db.session.rollback()
            print(f"Error deleting blog posts: {exc}")
            raise


if __name__ == "__main__":
    delete_blog_posts()
