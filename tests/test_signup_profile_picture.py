import io
import os
import tempfile

from sqlalchemy.pool import StaticPool
from PIL import Image

from app import create_app
from services.db import db
from services.models import User


def _make_app(upload_dir: str):
    return create_app(
        config_overrides={
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            },
            "UPLOAD_FOLDER_PROFILE_PICS": upload_dir,
        },
        seed_demo=False,
    )


def _png_bytes(size: tuple[int, int] = (64, 64)) -> bytes:
    image = Image.new("RGBA", size, color=(20, 150, 40, 255))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_signup_with_profile_picture_saves_uploaded_file():
    with tempfile.TemporaryDirectory() as upload_dir:
        app = _make_app(upload_dir)
        client = app.test_client()

        response = client.post(
            "/signup",
            data={
                "firstName": "Casey",
                "lastName": "User",
                "email": "casey@example.com",
                "username": "casey_user",
                "password": "supersecure123",
                "confirmPassword": "supersecure123",
                "dob": "2000-01-01",
                "gender": "other",
                "terms": "on",
                "profile_picture": (io.BytesIO(_png_bytes()), "avatar.png", "image/png"),
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

        with app.app_context():
            user = User.query.filter_by(username="casey_user").first()
            assert user is not None
            assert user.profile_image.endswith(".webp")
            assert os.path.exists(os.path.join(upload_dir, user.profile_image))
            db.session.remove()
            db.drop_all()
