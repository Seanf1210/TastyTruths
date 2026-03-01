import io
import os
import tempfile

from PIL import Image
from sqlalchemy.pool import StaticPool

from app import create_app
from services.db import db
from services.models import User


def _make_app(upload_dir: str | None = None):
    config = {
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "SQLALCHEMY_ENGINE_OPTIONS": {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        },
    }
    if upload_dir is not None:
        config["UPLOAD_FOLDER_PROFILE_PICS"] = upload_dir

    return create_app(
        config_overrides=config,
        seed_demo=False,
    )


def _login(client, user_id: int) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def _png_bytes(size: tuple[int, int] = (64, 64)) -> bytes:
    image = Image.new("RGBA", size, color=(60, 80, 220, 255))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


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


def test_owner_can_upload_picture_from_public_profile():
    with tempfile.TemporaryDirectory() as upload_dir:
        app = _make_app(upload_dir=upload_dir)
        client = app.test_client()

        with app.app_context():
            owner = User(username="owner", password_hash="placeholder")
            db.session.add(owner)
            db.session.commit()
            owner_id = owner.id

        _login(client, owner_id)
        response = client.post(
            "/profile/owner/picture",
            data={
                "profile_picture": (io.BytesIO(_png_bytes()), "avatar.png", "image/png"),
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile/owner")

        with app.app_context():
            updated = User.query.filter_by(username="owner").first()
            assert updated is not None
            assert updated.profile_image.endswith(".webp")
            assert os.path.exists(os.path.join(upload_dir, updated.profile_image))
            db.session.remove()
            db.drop_all()


def test_non_owner_cannot_upload_picture_for_another_user():
    with tempfile.TemporaryDirectory() as upload_dir:
        app = _make_app(upload_dir=upload_dir)
        client = app.test_client()

        with app.app_context():
            owner = User(username="owner", password_hash="placeholder")
            intruder = User(username="intruder", password_hash="placeholder")
            db.session.add_all([owner, intruder])
            db.session.commit()
            intruder_id = intruder.id

        _login(client, intruder_id)
        response = client.post(
            "/profile/owner/picture",
            data={
                "profile_picture": (io.BytesIO(_png_bytes()), "avatar.png", "image/png"),
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 403

        with app.app_context():
            owner_after = User.query.filter_by(username="owner").first()
            assert owner_after is not None
            assert owner_after.profile_image == "default.png"
            db.session.remove()
            db.drop_all()


def test_public_profile_avatar_upload_control_only_visible_to_owner():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        owner = User(username="owner", password_hash="placeholder")
        viewer = User(username="viewer", password_hash="placeholder")
        db.session.add_all([owner, viewer])
        db.session.commit()
        owner_id = owner.id
        viewer_id = viewer.id

    _login(client, owner_id)
    owner_view = client.get("/profile/owner")
    owner_body = owner_view.data.decode("utf-8")
    assert owner_view.status_code == 200
    assert "avatar-upload-form" in owner_body

    _login(client, viewer_id)
    non_owner_view = client.get("/profile/owner")
    non_owner_body = non_owner_view.data.decode("utf-8")
    assert non_owner_view.status_code == 200
    assert "avatar-upload-form" not in non_owner_body

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_owner_can_update_bio_experience_and_dietary_sections():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        owner = User(username="owner", password_hash="placeholder")
        db.session.add(owner)
        db.session.commit()
        owner_id = owner.id

    _login(client, owner_id)
    bio_response = client.post(
        "/profile/owner/bio",
        data={"bio": "Updated bio from profile section"},
        follow_redirects=False,
    )
    experience_response = client.post(
        "/profile/owner/experience",
        data={"experience": "10 years in kitchen operations.\nMenu planning."},
        follow_redirects=False,
    )
    dietary_response = client.post(
        "/profile/owner/dietary",
        data={
            "dietary_restrictions": ["vegan", "nut-free"],
            "custom_restriction": "low sodium",
        },
        follow_redirects=False,
    )

    assert bio_response.status_code == 302
    assert experience_response.status_code == 302
    assert dietary_response.status_code == 302

    profile_response = client.get("/profile/owner")
    body = profile_response.data.decode("utf-8")
    assert profile_response.status_code == 200
    assert "Updated bio from profile section" in body
    assert "10 years in kitchen operations." in body
    assert "vegan" in body
    assert "low sodium" in body

    with app.app_context():
        owner_after = User.query.filter_by(username="owner").first()
        assert owner_after is not None
        assert owner_after.bio == "Updated bio from profile section"
        assert owner_after.experience.startswith("10 years in kitchen operations.")
        assert owner_after.dietary_restrictions == ["vegan", "nut-free", "low sodium"]
        db.session.remove()
        db.drop_all()


def test_non_owner_cannot_update_profile_sections():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        owner = User(username="owner", password_hash="placeholder")
        intruder = User(username="intruder", password_hash="placeholder")
        db.session.add_all([owner, intruder])
        db.session.commit()
        intruder_id = intruder.id

    _login(client, intruder_id)
    bio_response = client.post("/profile/owner/bio", data={"bio": "hijack"}, follow_redirects=False)
    experience_response = client.post(
        "/profile/owner/experience",
        data={"experience": "hijack"},
        follow_redirects=False,
    )
    dietary_response = client.post(
        "/profile/owner/dietary",
        data={"dietary_restrictions": ["vegan"]},
        follow_redirects=False,
    )

    assert bio_response.status_code == 403
    assert experience_response.status_code == 403
    assert dietary_response.status_code == 403

    with app.app_context():
        owner_after = User.query.filter_by(username="owner").first()
        assert owner_after is not None
        assert (owner_after.bio or "") == ""
        assert (owner_after.experience or "") == ""
        assert owner_after.dietary_restrictions == []
        db.session.remove()
        db.drop_all()
