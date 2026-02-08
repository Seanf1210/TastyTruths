import pytest

from utilities.nutrition import compute_total_nutrition


def test_simple_recipe_totals():
    ingredients = [
        {
            "quantity_g": 100,
            "nutrition_per_gram": {
                "calories": 2,
                "protein_g": 0.1,
                "fat_g": 0.05,
                "carbs_g": 0.3,
            },
        },
        {
            "quantity_g": 50,
            "nutrition_per_gram": {
                "calories": 1,
                "protein_g": 0.2,
                "fat_g": 0.0,
                "carbs_g": 0.1,
            },
        },
    ]

    totals = compute_total_nutrition(ingredients)

    assert totals == {
        "calories": 250.0,
        "protein_g": 20.0,
        "fat_g": 5.0,
        "carbs_g": 35.0,
    }


def test_missing_nutrition_is_ignored():
    ingredients = [
        {"quantity_g": 100},
        {
            "quantity_g": 25,
            "nutrition_per_gram": {
                "calories": 3,
                "protein_g": 0.4,
                "fat_g": 0.2,
                "carbs_g": 0.1,
            },
        },
    ]

    totals = compute_total_nutrition(ingredients)

    assert totals == {
        "calories": 75.0,
        "protein_g": 10.0,
        "fat_g": 5.0,
        "carbs_g": 2.5,
    }


def test_zero_quantity_does_not_change_totals():
    ingredients = [
        {
            "quantity_g": 0,
            "nutrition_per_gram": {
                "calories": 10,
                "protein_g": 1,
                "fat_g": 1,
                "carbs_g": 1,
            },
        },
        {
            "quantity_g": 10,
            "nutrition_per_gram": {
                "calories": 2,
                "protein_g": 0.1,
                "fat_g": 0.05,
                "carbs_g": 0.2,
            },
        },
    ]

    totals = compute_total_nutrition(ingredients)

    assert totals == {
        "calories": 20.0,
        "protein_g": 1.0,
        "fat_g": 0.5,
        "carbs_g": 2.0,
    }
