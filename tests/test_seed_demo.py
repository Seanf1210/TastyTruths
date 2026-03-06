from sqlalchemy.pool import StaticPool

from app import create_app
from services.db import db
from services.models import Recipe, User


def _make_app():
    return create_app(
        config_overrides={
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            },
        },
        seed_demo=True,
    )


def test_seed_demo_creates_documented_demo_users_and_recipes():
    app = _make_app()
    with app.app_context():
        usernames = {
            user.username
            for user in User.query.filter(
                User.username.in_(
                    [
                        "demo_user",
                        "demo_admin",
                        "demo_moderator",
                        "demo_social",
                        "demo_one_friend",
                        "demo_three_friends",
                    ]
                )
            ).all()
        }

        assert usernames == {
            "demo_user",
            "demo_admin",
            "demo_moderator",
            "demo_social",
            "demo_one_friend",
            "demo_three_friends",
        }

        recipe_authors = {
            username
            for (username,) in (
                db.session.query(User.username)
                .join(Recipe, Recipe.author_id == User.id)
                .distinct()
                .all()
            )
        }
        assert {
            "demo_user",
            "demo_admin",
            "demo_moderator",
            "demo_social",
            "demo_one_friend",
            "demo_three_friends",
        }.issubset(recipe_authors)

        db.session.remove()
        db.drop_all()
