import json
from pathlib import Path

from services.nutrition import (
    compute_recipe_macros,
    convert_to_grams,
    ensure_ingredient_exists_in_assets,
    load_ingredient_index,
    normalize_ingredient_name,
)


def _write_assets(path: Path, items):
    with path.open("w", encoding="utf-8") as handle:
        json.dump(items, handle, indent=2)
        handle.write("\n")


def test_normalize_ingredient_name():
    assert normalize_ingredient_name("  Greek Yogurt  ") == "greek yogurt"
    assert normalize_ingredient_name("Chicken, Breast.") == "chicken breast"


def test_convert_to_grams_with_weight_units():
    grams, issue = convert_to_grams(2, "kg", {})
    assert issue is None
    assert grams == 2000.0

    grams, issue = convert_to_grams(4, "oz", {})
    assert issue is None
    assert round(grams, 4) == 113.398

    grams, issue = convert_to_grams(1, "lb", {})
    assert issue is None
    assert round(grams, 3) == 453.592


def test_convert_to_grams_with_entry_units():
    grams, issue = convert_to_grams(2, "cups", {"grams_per_cup": 120})
    assert issue is None
    assert grams == 240.0


def test_compute_recipe_macros_per_gram(tmp_path: Path):
    assets_path = tmp_path / "ingredients.json"
    _write_assets(
        assets_path,
        [
            {"_comment": "test"},
            {
                "id": "oats",
                "name": "Oats",
                "category": "grain",
                "dietary_restrictions": ["vegan"],
                "nutrition_per_gram": {
                    "calories": 3.0,
                    "protein_g": 0.1,
                    "fat_g": 0.05,
                    "carbs_g": 0.2,
                },
            },
        ],
    )
    index = load_ingredient_index(assets_path)
    totals, incomplete = compute_recipe_macros(
        [{"name": "Oats", "quantity": 100, "unit": "g"}],
        index,
    )
    assert incomplete is False
    assert totals["calories_kcal"] == 300.0
    assert totals["protein_g"] == 10.0
    assert totals["fat_g"] == 5.0
    assert totals["carbs_g"] == 20.0


def test_ensure_ingredient_exists_in_assets(tmp_path: Path):
    assets_path = tmp_path / "ingredients.json"
    _write_assets(
        assets_path,
        [
            {"_comment": "test"},
            {
                "id": "oats",
                "name": "Oats",
                "category": "grain",
                "dietary_restrictions": ["vegan"],
                "nutrition_per_gram": {
                    "calories": 3.0,
                    "protein_g": 0.1,
                    "fat_g": 0.05,
                    "carbs_g": 0.2,
                },
            },
        ],
    )

    ensure_ingredient_exists_in_assets("Greek yogurt", assets_path)
    data = json.loads(assets_path.read_text(encoding="utf-8"))
    names = [entry.get("name") for entry in data if isinstance(entry, dict)]
    assert "Greek yogurt" in names

    ensure_ingredient_exists_in_assets("Greek yogurt", assets_path)
    data_again = json.loads(assets_path.read_text(encoding="utf-8"))
    names_again = [entry.get("name") for entry in data_again if isinstance(entry, dict)]
    assert names_again.count("Greek yogurt") == 1
