from sqlalchemy.pool import StaticPool
import re

from app import create_app
from services.db import db
from services.models import Recipe, User


def _create_user(username: str, role: str = "normal") -> User:
    user = User(username=username, password_hash="placeholder", role=role)
    db.session.add(user)
    db.session.flush()
    return user


def _create_recipe(title: str, author_id: int | None) -> Recipe:
    recipe = Recipe(title=title, author_id=author_id, content=f"{title} content")
    db.session.add(recipe)
    db.session.flush()
    return recipe


def _login(client, user_id: int) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def _make_app(csrf_enabled: bool = False):
    return create_app(
        config_overrides={
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            },
            "WTF_CSRF_ENABLED": csrf_enabled,
        },
        seed_demo=False,
    )


def _extract_csrf_token(html: str) -> str:
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def test_normal_user_cannot_delete_other_users_recipe():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        owner = _create_user("owner_user", role="normal")
        user = _create_user("normal_user", role="normal")
        recipe = _create_recipe("Recipe", author_id=owner.id)
        db.session.commit()

    _login(client, user.id)
    resp = client.post(f"/recipes/{recipe.id}/delete", follow_redirects=False)

    assert resp.status_code in (302, 403)

    with app.app_context():
        assert db.session.get(Recipe, recipe.id) is not None
        db.session.remove()
        db.drop_all()


def test_recipe_owner_can_delete_recipe():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        owner = _create_user("owner_user", role="normal")
        recipe = _create_recipe("Recipe", author_id=owner.id)
        db.session.commit()

    _login(client, owner.id)
    resp = client.post(f"/recipes/{recipe.id}/delete", follow_redirects=False)

    assert resp.status_code in (302, 200)

    with app.app_context():
        assert db.session.get(Recipe, recipe.id) is None
        db.session.remove()
        db.drop_all()


def test_moderator_can_delete_recipe():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        mod = _create_user("moderator", role="moderator")
        recipe = _create_recipe("Recipe", author_id=None)
        db.session.commit()

    _login(client, mod.id)
    resp = client.post(f"/recipes/{recipe.id}/delete", follow_redirects=False)

    assert resp.status_code in (302, 200)

    with app.app_context():
        assert db.session.get(Recipe, recipe.id) is None
        db.session.remove()
        db.drop_all()


def test_recipe_delete_requires_valid_csrf_token():
    app = _make_app(csrf_enabled=True)
    client = app.test_client()

    with app.app_context():
        owner = _create_user("owner_user", role="normal")
        recipe = _create_recipe("Recipe", author_id=owner.id)
        db.session.commit()

    _login(client, owner.id)
    detail = client.get(f"/recipes/{recipe.id}-{recipe.slug}")
    assert detail.status_code == 200
    token = _extract_csrf_token(detail.get_data(as_text=True))

    resp = client.post(
        f"/recipes/{recipe.id}/delete",
        data={"csrf_token": token},
        follow_redirects=False,
    )

    assert resp.status_code in (302, 200)

    with app.app_context():
        assert db.session.get(Recipe, recipe.id) is None
        db.session.remove()
        db.drop_all()


def test_moderator_cannot_delete_account():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        mod = _create_user("moderator", role="moderator")
        target = _create_user("victim", role="normal")
        db.session.commit()

    _login(client, mod.id)
    resp = client.post(f"/users/{target.id}/delete", follow_redirects=False)

    assert resp.status_code in (302, 403)

    with app.app_context():
        assert db.session.get(User, target.id) is not None
        db.session.remove()
        db.drop_all()


def test_admin_can_delete_account():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        admin = _create_user("admin", role="admin")
        target = _create_user("victim", role="normal")
        db.session.commit()

    _login(client, admin.id)
    resp = client.post(f"/users/{target.id}/delete", follow_redirects=False)

    assert resp.status_code in (302, 200)

    with app.app_context():
        assert db.session.get(User, target.id) is None
        db.session.remove()
        db.drop_all()


def test_admin_override_can_delete_account():
    app = create_app(
        admin_override=True,
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
    client = app.test_client()

    with app.app_context():
        target = _create_user("victim", role="normal")
        db.session.commit()

    resp = client.post(f"/users/{target.id}/delete", follow_redirects=False)

    assert resp.status_code in (302, 200)

    with app.app_context():
        assert db.session.get(User, target.id) is None
        db.session.remove()
        db.drop_all()
