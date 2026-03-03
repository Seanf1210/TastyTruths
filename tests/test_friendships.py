from sqlalchemy.pool import StaticPool

from app import create_app
from services.db import db
from services.models import User, Friendship


def _make_app():
    return create_app(
        config_overrides={
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            },
            "WTF_CSRF_ENABLED": False,
        },
        seed_demo=False,
    )


def _create_user(username: str) -> User:
    user = User(username=username, password_hash="placeholder")
    db.session.add(user)
    db.session.flush()
    return user


def _cleanup_db():
    db.session.remove()
    db.drop_all()


def test_can_add_friend_creates_two_rows_and_returns_true():
    app = _make_app()

    with app.app_context():
        user = _create_user("alice")
        friend = _create_user("bob")
        db.session.commit()

        created, _ = user.add_friend(friend)

        assert created is True
        rows = Friendship.query.all()
        assert len(rows) == 2
        assert {(rows[0].user_id, rows[0].friend_id), (rows[1].user_id, rows[1].friend_id)} == {
            (user.id, friend.id),
            (friend.id, user.id),
        }
        assert [u.username for u in user.list_friends()] == ["bob"]

        _cleanup_db()


def test_adding_duplicate_friend_does_not_create_duplicates():
    app = _make_app()

    with app.app_context():
        user = _create_user("alice")
        friend = _create_user("bob")
        db.session.commit()

        created, _ = user.add_friend(friend)
        created_again, message = user.add_friend(friend)

        assert created is True
        assert created_again is False
        assert "friend" in message.lower()
        rows = Friendship.query.all()
        assert len(rows) == 2

        _cleanup_db()


def test_remove_friend_deletes_both_rows():
    app = _make_app()

    with app.app_context():
        user = _create_user("alice")
        friend = _create_user("bob")
        db.session.commit()

        user.add_friend(friend)
        removed = user.remove_friend(friend)

        assert removed is True
        assert Friendship.query.count() == 0

        _cleanup_db()


def test_cannot_friend_self():
    app = _make_app()

    with app.app_context():
        user = _create_user("alice")
        db.session.commit()

        created, message = user.add_friend(user)

        assert created is False
        assert "yourself" in message.lower()
        assert Friendship.query.count() == 0

        _cleanup_db()
