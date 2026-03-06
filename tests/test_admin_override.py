from sqlalchemy.pool import StaticPool

from app import AdminOverrideUser, create_app
from services.db import db
from services.models import User


def _make_app():
    return create_app(
        admin_override=True,
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


def test_admin_override_profile_routes_render_with_user_fields():
    app = _make_app()
    client = app.test_client()

    profile_page = client.get("/profile_page")
    public_profile = client.get(f"/profile/{AdminOverrideUser.OVERRIDE_USERNAME}")

    assert profile_page.status_code == 200
    assert public_profile.status_code == 200

    profile_body = profile_page.data.decode("utf-8")
    public_body = public_profile.data.decode("utf-8")
    assert AdminOverrideUser.OVERRIDE_USERNAME in profile_body
    assert AdminOverrideUser.OVERRIDE_USERNAME in public_body
    assert "Admin override account" in profile_body

    with app.app_context():
        override_user = User.query.filter_by(username=AdminOverrideUser.OVERRIDE_USERNAME).first()
        assert override_user is not None
        assert isinstance(override_user.id, int)
        assert override_user.role == "admin"
        db.session.remove()
        db.drop_all()


def test_admin_override_can_update_profile_fields_like_normal_user():
    app = _make_app()
    client = app.test_client()

    bio_response = client.post(
        "/profile/bio",
        data={"bio": "Override bio"},
        follow_redirects=False,
    )
    experience_response = client.post(
        "/profile/experience",
        data={"experience": "Override experience"},
        follow_redirects=False,
    )
    dietary_response = client.post(
        "/profile/dietary",
        data={
            "dietary_restrictions": ["vegan"],
            "custom_restriction": "low sodium",
        },
        follow_redirects=False,
    )

    assert bio_response.status_code == 302
    assert experience_response.status_code == 302
    assert dietary_response.status_code == 302

    refreshed = client.get("/profile_page")
    body = refreshed.data.decode("utf-8")
    assert refreshed.status_code == 200
    assert "Override bio" in body
    assert "Override experience" in body
    assert "vegan" in body
    assert "low sodium" in body

    with app.app_context():
        override_user = User.query.filter_by(username=AdminOverrideUser.OVERRIDE_USERNAME).first()
        assert override_user is not None
        assert override_user.bio == "Override bio"
        assert override_user.experience == "Override experience"
        assert override_user.dietary_restrictions == ["vegan", "low sodium"]
        db.session.remove()
        db.drop_all()
