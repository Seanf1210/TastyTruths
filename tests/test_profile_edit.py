import io
import os
import tempfile

from sqlalchemy.pool import StaticPool
from PIL import Image

from app import create_app
from services.db import db
from services.models import User


def _make_app(*, upload_dir=None, max_content_length=None):
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
    if max_content_length is not None:
        config["MAX_CONTENT_LENGTH"] = max_content_length

    return create_app(config_overrides=config, seed_demo=False)


def _login(client, user_id: int) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def _upload_payload(name: str, content: bytes = b"image-bytes", content_type: str = "image/png"):
    return {
        "bio": "Updated bio",
        "experiences_text": "Line cook\nRecipe tester\n",
        "profile_picture": (io.BytesIO(content), name, content_type),
    }


def _image_bytes(fmt: str = "PNG", size: tuple[int, int] = (64, 64)) -> bytes:
    mode = "RGBA" if fmt in {"PNG", "WEBP"} else "RGB"
    color = (200, 30, 30, 255) if mode == "RGBA" else (200, 30, 30)
    image = Image.new(mode, size, color=color)
    buf = io.BytesIO()
    image.save(buf, format=fmt)
    return buf.getvalue()


def test_logged_in_user_can_get_and_post_own_profile_edit():
    with tempfile.TemporaryDirectory() as upload_dir:
        app = _make_app(upload_dir=upload_dir)
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
            data=_upload_payload("avatar.png", _image_bytes("PNG"), "image/png"),
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert post_response.status_code == 302
        assert post_response.headers["Location"].endswith("/profile/owner")

        with app.app_context():
            saved = User.query.filter_by(username="owner").first()
            assert saved is not None
            assert saved.profile_image.endswith(".webp")
            assert saved.bio == "Updated bio"
            assert saved.experiences == ["Line cook", "Recipe tester"]
            assert os.path.exists(os.path.join(upload_dir, saved.profile_image))

        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_logged_out_user_cannot_access_profile_edit_routes():
    with tempfile.TemporaryDirectory() as upload_dir:
        app = _make_app(upload_dir=upload_dir)
        client = app.test_client()

        with app.app_context():
            user = User(username="owner", password_hash="placeholder")
            db.session.add(user)
            db.session.commit()

        get_response = client.get("/profile/owner/edit", follow_redirects=False)
        post_response = client.post(
            "/profile/owner/edit",
            data=_upload_payload("avatar.png", _image_bytes("PNG"), "image/png"),
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert get_response.status_code == 401
        assert post_response.status_code == 401

        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_logged_in_user_cannot_edit_another_users_profile():
    with tempfile.TemporaryDirectory() as upload_dir:
        app = _make_app(upload_dir=upload_dir)
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
            data=_upload_payload("avatar.png"),
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert get_response.status_code == 403
        assert post_response.status_code == 403

        with app.app_context():
            owner_after = db.session.get(User, owner_id)
            assert owner_after is not None
            assert owner_after.bio == "Original bio"
            assert owner_after.experiences == ["Original experience"]
            assert owner_after.profile_image == "default.png"

        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_moderator_cannot_edit_another_users_profile():
    with tempfile.TemporaryDirectory() as upload_dir:
        app = _make_app(upload_dir=upload_dir)
        client = app.test_client()

        with app.app_context():
            owner = User(
                username="owner",
                password_hash="placeholder",
                bio="Original bio",
                experiences=["Original experience"],
            )
            moderator = User(username="mod", password_hash="placeholder", role="moderator")
            db.session.add_all([owner, moderator])
            db.session.commit()
            mod_id = moderator.id

        _login(client, mod_id)
        response = client.post(
            "/profile/owner/edit",
            data=_upload_payload("avatar.png", _image_bytes("PNG"), "image/png"),
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 403

        with app.app_context():
            updated = User.query.filter_by(username="owner").first()
            assert updated is not None
            assert updated.profile_image == "default.png"
            assert updated.bio == "Original bio"
            assert updated.experiences == ["Original experience"]
            db.session.remove()
            db.drop_all()


def test_uploading_new_picture_replaces_old_and_ignores_missing_old_file():
    with tempfile.TemporaryDirectory() as upload_dir:
        app = _make_app(upload_dir=upload_dir)
        client = app.test_client()

        with app.app_context():
            user = User(username="owner", password_hash="placeholder")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

        _login(client, user_id)

        first_upload = client.post(
            "/profile/owner/edit",
            data=_upload_payload("first.png", _image_bytes("PNG"), "image/png"),
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert first_upload.status_code == 302

        with app.app_context():
            saved = User.query.filter_by(username="owner").first()
            first_name = saved.profile_image
            first_path = os.path.join(upload_dir, first_name)
            assert os.path.exists(first_path)

        # Simulate manual cleanup so old file is missing on next replacement.
        os.remove(first_path)
        assert not os.path.exists(first_path)

        second_upload = client.post(
            "/profile/owner/edit",
            data=_upload_payload("second.jpg", _image_bytes("JPEG"), "image/jpeg"),
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert second_upload.status_code == 302

        with app.app_context():
            updated = User.query.filter_by(username="owner").first()
            assert updated.profile_image != first_name
            assert updated.profile_image.endswith(".webp")
            assert os.path.exists(os.path.join(upload_dir, updated.profile_image))

        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_profile_image_persists_after_logout_and_login():
    with tempfile.TemporaryDirectory() as upload_dir:
        app = _make_app(upload_dir=upload_dir)
        client = app.test_client()

        with app.app_context():
            user = User(username="owner", password_hash="placeholder")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

        _login(client, user_id)
        upload_response = client.post(
            "/profile/owner/edit",
            data=_upload_payload("persist.webp", _image_bytes("WEBP"), "image/webp"),
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert upload_response.status_code == 302

        with app.app_context():
            saved = User.query.filter_by(username="owner").first()
            saved_filename = saved.profile_image

        client.get("/logout", follow_redirects=False)
        _login(client, user_id)

        profile_response = client.get("/profile/owner")
        body = profile_response.data.decode("utf-8")

        assert profile_response.status_code == 200
        assert f"/static/uploads/profile_pics/{saved_filename}" in body

        with app.app_context():
            persisted = User.query.filter_by(username="owner").first()
            assert persisted.profile_image == saved_filename

        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_invalid_file_extension_is_rejected():
    with tempfile.TemporaryDirectory() as upload_dir:
        app = _make_app(upload_dir=upload_dir)
        client = app.test_client()

        with app.app_context():
            user = User(username="owner", password_hash="placeholder")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

        _login(client, user_id)
        response = client.post(
            "/profile/owner/edit",
            data=_upload_payload("not-an-image.txt", b"text-data", "text/plain"),
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 400
        body = response.data.decode("utf-8")
        assert "Only PNG/JPG/JPEG/WEBP allowed." in body

        with app.app_context():
            saved = User.query.filter_by(username="owner").first()
            assert saved.profile_image == "default.png"

        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_oversized_profile_picture_is_rejected():
    with tempfile.TemporaryDirectory() as upload_dir:
        app = _make_app(upload_dir=upload_dir, max_content_length=1024)
        client = app.test_client()

        with app.app_context():
            user = User(username="owner", password_hash="placeholder")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

        _login(client, user_id)
        response = client.post(
            "/profile/owner/edit",
            data={
                "bio": "Updated bio",
                "experiences_text": "Line cook",
                "profile_picture": (
                    io.BytesIO(b"a" * 3000),
                    "too-big.png",
                    "image/png",
                ),
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile/owner")

        with app.app_context():
            saved = User.query.filter_by(username="owner").first()
            assert saved.profile_image == "default.png"

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
    assert "avatar-upload-form" in own_body

    assert other_profile.status_code == 200
    assert "avatar-upload-form" not in other_body

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_staff_user_cannot_see_edit_controls_on_other_profile():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        owner = User(username="owner", password_hash="placeholder")
        moderator = User(username="mod", password_hash="placeholder", role="moderator")
        db.session.add_all([owner, moderator])
        db.session.commit()
        mod_id = moderator.id

    _login(client, mod_id)
    other_profile = client.get("/profile/owner")
    other_body = other_profile.data.decode("utf-8")

    assert other_profile.status_code == 200
    assert "avatar-upload-form" not in other_body

    with app.app_context():
        db.session.remove()
        db.drop_all()
