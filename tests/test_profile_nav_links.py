from sqlalchemy.pool import StaticPool

from app import create_app
from services.db import db
from services.models import User


def _login(client, user_id: int) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


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
        seed_demo=False,
    )


def test_footer_profile_link_points_to_public_profile_when_logged_in():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        user = User(username="chef_nav", password_hash="placeholder")
        db.session.add(user)
        db.session.commit()

    _login(client, user.id)
    response = client.get("/")
    body = response.data.decode("utf-8")

    expected_href = '/profile/chef_nav'
    assert response.status_code == 200
    assert 'class="nav-profile-link"' not in body
    assert f'href="{expected_href}" class="footer-profile-link"' in body

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_footer_profile_link_points_to_login_when_logged_out():
    app = _make_app()
    client = app.test_client()

    response = client.get("/")
    body = response.data.decode("utf-8")

    assert response.status_code == 200
    assert 'class="nav-profile-link"' not in body
    assert 'href="/login" class="footer-profile-link"' in body

    with app.app_context():
        db.session.remove()
        db.drop_all()
