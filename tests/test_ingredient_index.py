import json
from pathlib import Path

import services.ingredient_index as ingredient_index


def _write_assets(path: Path, items):
    with path.open("w", encoding="utf-8") as handle:
        json.dump(items, handle, indent=2)
        handle.write("\n")


def test_search_suggestions_ranking(monkeypatch, tmp_path: Path):
    assets_path = tmp_path / "ingredients.json"
    _write_assets(
        assets_path,
        [
            {"id": "butter", "name": "Butter", "aliases": ["unsalted butter"]},
            {"id": "peanut_butter", "name": "Peanut Butter", "aliases": ["butter of peanuts"]},
            {"id": "butternut_squash", "name": "Butternut Squash", "aliases": []},
        ],
    )

    monkeypatch.setattr(ingredient_index, "ASSETS_INGREDIENTS_PATH", assets_path)
    ingredient_index._CACHE["mtime"] = None
    ingredient_index._CACHE["index"] = None

    results = ingredient_index.search_suggestions("butte", limit=5)
    names = [item["name"] for item in results]
    assert names[0] == "Butter"
    assert "Peanut Butter" in names
    assert "Butternut Squash" in names


def test_match_ingredient_id_by_alias(monkeypatch, tmp_path: Path):
    assets_path = tmp_path / "ingredients.json"
    _write_assets(
        assets_path,
        [
            {"id": "yogurt_greek", "name": "Greek Yogurt", "aliases": ["greek yogurt"]},
        ],
    )
    monkeypatch.setattr(ingredient_index, "ASSETS_INGREDIENTS_PATH", assets_path)
    ingredient_index._CACHE["mtime"] = None
    ingredient_index._CACHE["index"] = None

    index = ingredient_index.load_ingredients_index()
    assert ingredient_index.match_ingredient_id("Greek yogurt", index) == "yogurt_greek"
