from app import create_app
from services.db import db
from services.models import User


def _make_app():
    return create_app(
        config_overrides={
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        },
        seed_demo=False,
    )


def test_public_profile_existing_user_returns_200():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        user = User(
            username="CaseUser",
            password_hash="placeholder",
            bio="Public bio text",
            experiences=["Line cook", "Baker"],
        )
        db.session.add(user)
        db.session.commit()

    response = client.get("/profile/caseuser")
    body = response.data.decode("utf-8")

    assert response.status_code == 200
    assert "CaseUser" in body
    assert "Public bio text" in body
    assert "Line cook" in body


def test_public_profile_missing_user_returns_404():
    app = _make_app()
    client = app.test_client()

    response = client.get("/profile/does-not-exist")
    assert response.status_code == 404


def test_public_profile_uses_default_avatar_when_missing_profile_image():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        user = User(username="noavatar", password_hash="placeholder", bio="Hello")
        db.session.add(user)
        db.session.commit()

    response = client.get("/profile/noavatar")
    body = response.data.decode("utf-8")

    assert response.status_code == 200
    assert "/static/uploads/profile_pics/default.png" in body


def test_public_profile_does_not_display_email_or_access_level():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        user = User(
            username="privateuser",
            password_hash="placeholder",
            email="private@example.com",
            role="admin",
            bio="Visible bio",
            experiences=["Community helper"],
        )
        db.session.add(user)
        db.session.commit()

    response = client.get("/profile/privateuser")
    body = response.data.decode("utf-8")

    assert response.status_code == 200
    assert "private@example.com" not in body
    assert "admin" not in body
