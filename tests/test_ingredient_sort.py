import pytest
from sqlalchemy.pool import StaticPool

from app import create_app
from services.db import db
from services.ingredients import ALLOWED_NUTRIENT_SORT_KEYS
from services.models import Ingredient


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


def _reset_ingredients():
    Ingredient.query.delete()
    db.session.commit()


@pytest.mark.parametrize("key", ALLOWED_NUTRIENT_SORT_KEYS.keys())
def test_sort_each_key_orders_correctly(client, app, key):
    with app.app_context():
        _reset_ingredients()
        db.session.add_all(
            [
                Ingredient(name="Alpha", nutrition_per_100g={key: 3}),
                Ingredient(name="Bravo", nutrition_per_100g={key: 2}),
                Ingredient(name="Charlie", nutrition_per_100g={key: 1}),
                Ingredient(name="Missing", nutrition_per_100g={}),
            ]
        )
        db.session.commit()

    res = client.get(f"/api/ingredients?sort_key={key}&sort_dir=desc")
    assert res.status_code == 200
    names = [row["name"] for row in res.get_json()]
    assert names == ["Alpha", "Bravo", "Charlie", "Missing"]

    res = client.get(f"/api/ingredients?sort_key={key}&sort_dir=asc")
    assert res.status_code == 200
    names = [row["name"] for row in res.get_json()]
    assert names == ["Charlie", "Bravo", "Alpha", "Missing"]


def test_missing_values_always_sort_last(client, app):
    key = "protein_g"
    with app.app_context():
        _reset_ingredients()
        db.session.add_all(
            [
                Ingredient(name="HasValue", nutrition_per_100g={key: 5}),
                Ingredient(name="Missing", nutrition_per_100g={}),
                Ingredient(name="Lower", nutrition_per_100g={key: 1}),
            ]
        )
        db.session.commit()

    res = client.get(f"/api/ingredients?sort_key={key}&sort_dir=desc")
    assert res.status_code == 200
    names = [row["name"] for row in res.get_json()]
    assert names[-1] == "Missing"

    res = client.get(f"/api/ingredients?sort_key={key}&sort_dir=asc")
    assert res.status_code == 200
    names = [row["name"] for row in res.get_json()]
    assert names[-1] == "Missing"


def test_tie_breakers_are_stable(client, app):
    key = "protein_g"
    with app.app_context():
        _reset_ingredients()
        db.session.add_all(
            [
                Ingredient(name="apple", nutrition_per_100g={key: 10}),
                Ingredient(name="Apple", nutrition_per_100g={key: 10}),
                Ingredient(name="Banana", nutrition_per_100g={key: 10}),
                Ingredient(name="Cherry", nutrition_per_100g={key: 5}),
            ]
        )
        db.session.commit()

    res = client.get(f"/api/ingredients?sort_key={key}&sort_dir=desc")
    assert res.status_code == 200
    names = [row["name"] for row in res.get_json()]
    assert names == ["apple", "Apple", "Banana", "Cherry"]


def test_invalid_sort_key_returns_400(client, app):
    res = client.get("/api/ingredients?sort_key=not_a_key")
    assert res.status_code == 400
    payload = res.get_json()
    assert "allowed_keys" in payload
