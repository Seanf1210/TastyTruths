from sqlalchemy.pool import StaticPool

from app import create_app
from services.db import db
from services.models import User


def _create_user(username: str) -> User:
    user = User(username=username, password_hash="placeholder")
    db.session.add(user)
    db.session.flush()
    return user


def _login(client, user_id: int) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_unauthenticated_update_is_blocked():
    app = create_app(
        config_overrides={
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            },
        },
        seed_demo=False,
    )
    client = app.test_client()

    response = client.put(
        "/api/users/1/dietary-restrictions",
        json={"dietary_restrictions": ["vegan"]},
    )

    assert response.status_code in (302, 401)

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_user_cannot_update_another_users_restrictions():
    app = create_app(
        config_overrides={
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            },
        },
        seed_demo=False,
    )
    client = app.test_client()

    with app.app_context():
        user_a = _create_user("chef_a")
        user_b = _create_user("chef_b")
        db.session.commit()

    _login(client, user_a.id)
    response = client.put(
        f"/api/users/{user_b.id}/dietary-restrictions",
        json={"dietary_restrictions": ["vegan"]},
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == "forbidden"

    with app.app_context():
        reloaded = db.session.get(User, user_b.id)
        assert (reloaded.dietary_restrictions or []) == []
        db.session.remove()
        db.drop_all()


def test_validation_rejects_empty_and_max_limits_and_dedupes():
    app = create_app(
        config_overrides={
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            },
        },
        seed_demo=False,
    )
    client = app.test_client()

    with app.app_context():
        user = _create_user("chef_validation")
        db.session.commit()

    _login(client, user.id)

    empty_response = client.put(
        f"/api/users/{user.id}/dietary-restrictions",
        json={"dietary_restrictions": ["vegan", "  "]},
    )
    assert empty_response.status_code == 400
    assert "cannot include empty values" in empty_response.get_json()["error"]

    max_count_response = client.put(
        f"/api/users/{user.id}/dietary-restrictions",
        json={"dietary_restrictions": [f"tag-{i}" for i in range(21)]},
    )
    assert max_count_response.status_code == 400
    assert "up to 20 dietary restrictions" in max_count_response.get_json()["error"]

    too_long_response = client.put(
        f"/api/users/{user.id}/dietary-restrictions",
        json={"dietary_restrictions": ["x" * 33]},
    )
    assert too_long_response.status_code == 400
    assert "32 characters or fewer" in too_long_response.get_json()["error"]

    dedupe_response = client.put(
        f"/api/users/{user.id}/dietary-restrictions",
        json={"dietary_restrictions": [" Vegan ", "vegan", "Gluten-Free "]},
    )
    assert dedupe_response.status_code == 200
    assert dedupe_response.get_json()["dietary_restrictions"] == ["vegan", "gluten-free"]

    with app.app_context():
        reloaded = db.session.get(User, user.id)
        assert reloaded.dietary_restrictions == ["vegan", "gluten-free"]
        db.session.remove()
        db.drop_all()


def test_saved_restrictions_persist_and_are_shown_on_profile():
    app = create_app(
        config_overrides={
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            },
        },
        seed_demo=False,
    )
    client = app.test_client()

    with app.app_context():
        user = _create_user("chef_persist")
        db.session.commit()

    _login(client, user.id)
    save_response = client.put(
        f"/api/users/{user.id}/dietary-restrictions",
        json={"dietary_restrictions": ["vegan", "nut-free"]},
    )
    assert save_response.status_code == 200

    get_response = client.get(f"/api/users/{user.id}/dietary-restrictions")
    assert get_response.status_code == 200
    assert get_response.get_json()["dietary_restrictions"] == ["vegan", "nut-free"]

    profile_response = client.get("/profile_page")
    body = profile_response.data.decode("utf-8")
    assert profile_response.status_code == 200
    assert "Dietary Restrictions" in body
    assert "vegan" in body
    assert "nut-free" in body

    with app.app_context():
        reloaded = db.session.get(User, user.id)
        assert reloaded.dietary_restrictions == ["vegan", "nut-free"]
        db.session.remove()
        db.drop_all()
