import json

import pytest
from sqlalchemy.pool import StaticPool

from app import create_app
from services.db import db
from services.filtering import filter_ingredients_by_dietary_tags
from services.models import Ingredient, Recipe


def test_no_selected_tags_returns_all():
    ingredients = [
        {"name": "Oats", "dietary_tags": ["vegan"]},
        {"name": "Chicken", "dietary_tags": ["not_vegan"]},
    ]
    assert filter_ingredients_by_dietary_tags(ingredients, [], "or") == ingredients


def test_or_mode_matches_any():
    ingredients = [
        {"name": "Oats", "dietary_tags": ["vegan"]},
        {"name": "Milk", "dietary_tags": ["vegetarian"]},
        {"name": "Chicken", "dietary_tags": ["not_vegan"]},
    ]
    filtered = filter_ingredients_by_dietary_tags(
        ingredients, ["vegan", "vegetarian"], "or"
    )
    assert [i["name"] for i in filtered] == ["Oats", "Milk"]


def test_and_mode_matches_all():
    ingredients = [
        {"name": "Oats", "dietary_tags": ["vegan", "gluten-free"]},
        {"name": "Milk", "dietary_tags": ["vegetarian"]},
    ]
    filtered = filter_ingredients_by_dietary_tags(
        ingredients, ["vegan", "gluten-free"], "and"
    )
    assert [i["name"] for i in filtered] == ["Oats"]


def test_missing_tags_never_match():
    ingredients = [
        {"name": "Oats", "dietary_tags": ["vegan"]},
        {"name": "Mystery"},
    ]
    filtered = filter_ingredients_by_dietary_tags(ingredients, ["vegan"], "or")
    assert [i["name"] for i in filtered] == ["Oats"]


def test_normalization_and_invalid_mode_defaults_to_or():
    ingredients = [
        {"name": "Oats", "dietary_tags": [" Vegan ", "Gluten-Free"]},
        {"name": "Chicken", "dietary_tags": ["not_vegan"]},
    ]
    filtered = filter_ingredients_by_dietary_tags(
        ingredients, ["  vegan", "GLUTEN-FREE "], "unknown"
    )
    assert [i["name"] for i in filtered] == ["Oats"]


@pytest.fixture()
def app():
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

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def test_recipe_detail_filters_ingredients(client, app):
    with app.app_context():
        oats = Ingredient(name="Oats")
        oats.set_dietary_tags(["vegan", "gluten-free"])
        chicken = Ingredient(name="Chicken")
        chicken.set_dietary_tags(["not_vegan"])
        db.session.add_all([oats, chicken])

        recipe = Recipe(
            title="Test Recipe",
            ingredients=json.dumps(
                [
                    {"name": "Oats", "quantity": 1, "unit": "cup"},
                    {"name": "Chicken", "quantity": 1, "unit": "lb"},
                ]
            ),
            instructions="Mix.",
        )
        db.session.add(recipe)
        db.session.commit()
        slug = f"{recipe.id}-{recipe.slug}"

    res = client.get(f"/recipes/{slug}?tags=vegan&mode=or")
    assert res.status_code == 200
    body = res.data.decode("utf-8")
    assert "Oats" in body
    assert "Chicken" not in body


def test_recipe_detail_empty_state_message(client, app):
    with app.app_context():
        oats = Ingredient(name="Oats")
        oats.set_dietary_tags(["vegan"])
        db.session.add(oats)
        recipe = Recipe(
            title="Empty Filter Recipe",
            ingredients=json.dumps([{"name": "Oats"}]),
            instructions="Mix.",
        )
        db.session.add(recipe)
        db.session.commit()
        slug = f"{recipe.id}-{recipe.slug}"

    res = client.get(f"/recipes/{slug}?tags=nut_free&mode=and")
    assert res.status_code == 200
    body = res.data.decode("utf-8")
    assert "No ingredients match your selected dietary filters." in body
