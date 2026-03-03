import io
import json
import os
import tempfile

from sqlalchemy.pool import StaticPool

from app import create_app
from services.db import db
from services.models import Recipe, User


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


def test_create_recipe_form_hidden_ingredients_not_required_in_html():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        user = User(username="chef_form", password_hash="placeholder")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    _login(client, user_id)
    response = client.get("/recipes/create")
    body = response.data.decode("utf-8")

    assert response.status_code == 200
    assert 'name="ingredients"' in body
    assert 'id="ingredient-client-error"' in body
    assert 'name="ingredients" required' not in body


def test_create_recipe_with_ingredient_rows_persists_and_redirects_to_detail():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        user = User(username="chef", password_hash="placeholder")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    _login(client, user_id)
    with app.app_context():
        before_count = Recipe.query.count()
    response = client.post(
        "/recipes/create",
        data={
            "title": "Weeknight Pasta",
            "instructions": "Boil water, cook pasta, toss with sauce.",
            "ingredient_name[]": ["Pasta", "Tomato sauce"],
            "ingredient_id[]": ["", ""],
            "ingredient_quantity[]": ["12", "2"],
            "ingredient_unit[]": ["oz", "cups"],
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/recipes/" in response.headers["Location"]

    with app.app_context():
        after_count = Recipe.query.count()
        created = Recipe.query.filter_by(title="Weeknight Pasta").first()
        assert after_count == before_count + 1
        assert created is not None
        assert created.author_id == user_id
        assert created.instructions == "Boil water, cook pasta, toss with sauce."

    detail_response = client.get(response.headers["Location"])
    body = detail_response.data.decode("utf-8")
    assert detail_response.status_code == 200
    assert "Weeknight Pasta" in body
    assert "Boil water, cook pasta, toss with sauce." in body



def test_create_recipe_with_ingredients_persists_structured_ingredient_rows():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        user = User(username="chef_ingredients", password_hash="placeholder")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    _login(client, user_id)
    response = client.post(
        "/recipes/create",
        data={
            "title": "Structured Ingredients",
            "instructions": "Combine and simmer for 20 minutes.",
            "ingredient_name[]": ["Lentils", "Vegetable stock"],
            "ingredient_id[]": ["", ""],
            "ingredient_quantity[]": ["2", "3"],
            "ingredient_unit[]": ["cups", "cups"],
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        created = Recipe.query.filter_by(title="Structured Ingredients").first()
        assert created is not None
        ingredient_rows = json.loads(created.ingredients)
        assert len(ingredient_rows) == 2
        assert ingredient_rows[0]["name"] == "Lentils"
        assert ingredient_rows[0]["quantity"] == "2"
        assert ingredient_rows[0]["unit"] == "cups"
        assert ingredient_rows[0]["ingredient_id"]
        assert ingredient_rows[1]["name"] == "Vegetable stock"
        assert ingredient_rows[1]["quantity"] == "3"
        assert ingredient_rows[1]["unit"] == "cups"
        assert ingredient_rows[1]["ingredient_id"]


def test_create_recipe_invalid_payload_returns_400_and_does_not_insert():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        user = User(username="chef", password_hash="placeholder")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    _login(client, user_id)
    response = client.post(
        "/recipes/create",
        data={
            "title": "No Instructions",
            "instructions": "",
            "ingredient_name[]": ["Salt"],
            "ingredient_id[]": [""],
            "ingredient_quantity[]": ["1"],
            "ingredient_unit[]": ["tsp"],
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "Instructions are required." in response.data.decode("utf-8")

    with app.app_context():
        assert Recipe.query.filter_by(title="No Instructions").first() is None


def test_create_recipe_with_image_saves_file_and_path():
    app = _make_app()
    client = app.test_client()

    with tempfile.TemporaryDirectory() as temp_static:
        app.static_folder = temp_static
        with app.app_context():
            user = User(username="chef_img", password_hash="placeholder")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

        _login(client, user_id)
        response = client.post(
            "/recipes/create",
            data={
                "title": "Image Recipe",
                "instructions": "Mix and bake until golden brown.",
                "ingredient_name[]": ["Flour"],
                "ingredient_id[]": [""],
                "ingredient_quantity[]": ["1"],
                "ingredient_unit[]": ["cup"],
                "image": (io.BytesIO(b"fake-jpg-bytes"), "dish.jpg"),
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        with app.app_context():
            created = Recipe.query.filter_by(title="Image Recipe").first()
            assert created is not None
            assert created.image_filename is not None
            assert created.image_filename.startswith("uploads/recipes/")
            saved_path = os.path.join(app.static_folder, created.image_filename.replace("/", os.sep))
            assert os.path.exists(saved_path)


def test_create_recipe_post_redirect_get_shows_created_recipe_content():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        user = User(username="chef_prg", password_hash="placeholder")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    _login(client, user_id)
    response = client.post(
        "/recipes/create",
        data={
            "title": "PRG Recipe",
            "instructions": "Step one and step two are clearly listed.",
            "ingredient_name[]": ["Rice"],
            "ingredient_id[]": [""],
            "ingredient_quantity[]": ["2"],
            "ingredient_unit[]": ["cups"],
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "PRG Recipe" in body
    assert "Step one and step two are clearly listed." in body


def test_create_recipe_missing_title_or_ingredients_returns_400_and_does_not_insert():
    app = _make_app()
    client = app.test_client()

    with app.app_context():
        user = User(username="chef_invalid", password_hash="placeholder")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    _login(client, user_id)
    missing_title = client.post(
        "/recipes/create",
        data={
            "title": "",
            "instructions": "Cook it.",
            "ingredient_name[]": ["Salt"],
            "ingredient_id[]": [""],
            "ingredient_quantity[]": ["1"],
            "ingredient_unit[]": ["tsp"],
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert missing_title.status_code == 400
    assert "Title is required." in missing_title.data.decode("utf-8")

    no_ingredients = client.post(
        "/recipes/create",
        data={
            "title": "No Ingredients",
            "instructions": "Cook it.",
            "ingredient_name[]": [""],
            "ingredient_id[]": [""],
            "ingredient_quantity[]": [""],
            "ingredient_unit[]": [""],
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert no_ingredients.status_code == 400
    assert "Please list at least one ingredient." in no_ingredients.data.decode("utf-8")

    with app.app_context():
        assert Recipe.query.filter_by(title="No Ingredients").first() is None
