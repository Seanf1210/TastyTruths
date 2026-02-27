from sqlalchemy.pool import StaticPool

from app import create_app
from services.db import db
from services.models import User


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


def _login(client, user_id: int) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_logged_in_user_can_get_and_post_own_profile_edit():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        user = User(username="owner", password_hash="placeholder")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    _login(client, user_id)
    get_response = client.get("/profile/owner/edit")
    assert get_response.status_code == 200

    post_response = client.post(
        "/profile/owner/edit",
        data={
            "profile_image_path": "https://example.com/avatar.png",
            "bio": "Updated bio",
            "experiences_text": "Line cook\nRecipe tester\n",
        },
        follow_redirects=False,
    )
    assert post_response.status_code == 302
    assert post_response.headers["Location"].endswith("/profile/owner")

    with app.app_context():
        saved = User.query.filter_by(username="owner").first()
        assert saved is not None
        assert saved.profile_image_path == "https://example.com/avatar.png"
        assert saved.bio == "Updated bio"
        assert saved.experiences == ["Line cook", "Recipe tester"]

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_logged_out_user_cannot_access_profile_edit_routes():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        user = User(username="owner", password_hash="placeholder")
        db.session.add(user)
        db.session.commit()

    get_response = client.get("/profile/owner/edit", follow_redirects=False)
    post_response = client.post(
        "/profile/owner/edit",
        data={"bio": "should not save"},
        follow_redirects=False,
    )

    assert get_response.status_code == 401
    assert post_response.status_code == 401

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_logged_in_user_cannot_edit_another_users_profile():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        owner = User(
            username="owner",
            password_hash="placeholder",
            bio="Original bio",
            experiences=["Original experience"],
        )
        intruder = User(username="intruder", password_hash="placeholder")
        db.session.add_all([owner, intruder])
        db.session.commit()
        owner_id = owner.id
        intruder_id = intruder.id

    _login(client, intruder_id)
    get_response = client.get("/profile/owner/edit", follow_redirects=False)
    post_response = client.post(
        "/profile/owner/edit",
        data={
            "bio": "Hacked bio",
            "experiences_text": "Hacked experience",
        },
        follow_redirects=False,
    )

    assert get_response.status_code == 403
    assert post_response.status_code == 403

    with app.app_context():
        owner_after = db.session.get(User, owner_id)
        assert owner_after is not None
        assert owner_after.bio == "Original bio"
        assert owner_after.experiences == ["Original experience"]

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_public_profile_shows_edit_button_only_when_viewing_self():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        owner = User(username="owner", password_hash="placeholder")
        other = User(username="other", password_hash="placeholder")
        db.session.add_all([owner, other])
        db.session.commit()
        owner_id = owner.id

    _login(client, owner_id)
    own_profile = client.get("/profile/owner")
    other_profile = client.get("/profile/other")
    own_body = own_profile.data.decode("utf-8")
    other_body = other_profile.data.decode("utf-8")

    assert own_profile.status_code == 200
    assert 'href="/profile/owner/edit"' in own_body
    assert "Edit Profile" in own_body

    assert other_profile.status_code == 200
    assert 'href="/profile/other/edit"' not in other_body

    with app.app_context():
        db.session.remove()
        db.drop_all()
