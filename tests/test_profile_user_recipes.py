from sqlalchemy.pool import StaticPool

from app import create_app
from services.db import db
from services.models import Recipe, User


def _create_user(username: str) -> User:
    user = User(username=username, password_hash="placeholder")
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


def test_profile_shows_only_authenticated_users_recipes():
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
        mine = _create_recipe("My Recipe", user_a.id)
        _create_recipe("Other User Recipe", user_b.id)
        _create_recipe("No Author Recipe", None)
        db.session.commit()
        expected_href = f'/recipes/{mine.id}-{mine.slug}'

    _login(client, user_a.id)
    response = client.get("/profile_page")
    body = response.data.decode("utf-8")

    assert response.status_code == 200
    assert "User-created recipes" in body
    assert "My Recipe" in body
    assert "Other User Recipe" not in body
    assert "No Author Recipe" not in body
    assert expected_href in body

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_profile_empty_state_when_no_user_recipes():
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
        user = _create_user("chef_empty")
        db.session.commit()

    _login(client, user.id)
    response = client.get("/profile_page")
    body = response.data.decode("utf-8")

    assert response.status_code == 200
    assert "User-created recipes" in body
    assert "This user has not created any recipes yet." in body

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_recipe_api_includes_author_avatar_for_recipe_cards():
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
        user = User(
            username="chef_avatar",
            password_hash="placeholder",
            profile_image="stock_alpaca.jpg",
        )
        db.session.add(user)
        db.session.flush()
        _create_recipe("Avatar Recipe", user.id)
        db.session.commit()

    response = client.get("/api/recipes")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload

    recipe_row = next(row for row in payload if row["title"] == "Avatar Recipe")
    assert recipe_row["author_name"] == "chef_avatar"
    assert recipe_row["author_username"] == "chef_avatar"
    assert recipe_row["author_avatar_url"].endswith("/uploads/profile_pics/stock_alpaca.jpg")
    assert recipe_row["display_title"] == "Avatar Recipe"

    with app.app_context():
        recipe = Recipe.query.filter_by(title="Avatar Recipe").first()
        recipe.title = "Avatar Recipe (chef_avatar)"
        db.session.commit()

    response = client.get("/api/recipes")
    payload = response.get_json()
    recipe_row = next(row for row in payload if row["title"] == "Avatar Recipe (chef_avatar)")
    assert recipe_row["display_title"] == "Avatar Recipe"

    with app.app_context():
        db.session.remove()
        db.drop_all()
