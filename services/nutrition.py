import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


ASSETS_INGREDIENTS_PATH = (
    Path(__file__).resolve().parents[1] / "assets" / "ingredients.json"
)


def normalize_ingredient_name(name: Optional[str]) -> str:
    if not name:
        return ""
    text = str(name).strip().lower()
    text = re.sub(r"\s+", " ", text)
    # Remove conservative punctuation differences (commas/periods).
    text = text.replace(",", "").replace(".", "")
    return text


def _slugify_id(name: str) -> str:
    base = normalize_ingredient_name(name)
    base = re.sub(r"[^a-z0-9]+", "_", base).strip("_")
    return base or "ingredient"


def load_ingredient_index(path: Path = ASSETS_INGREDIENTS_PATH) -> Dict[str, Dict]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    items = []
    for entry in data:
        if isinstance(entry, dict) and entry.get("name"):
            items.append(entry)

    by_name = {}
    by_id = {}
    for entry in items:
        name_key = normalize_ingredient_name(entry.get("name"))
        if name_key:
            by_name[name_key] = entry
        entry_id = entry.get("id")
        if entry_id:
            by_id[normalize_ingredient_name(entry_id)] = entry

    return {"items": items, "by_name": by_name, "by_id": by_id, "raw": data}


def ensure_ingredient_exists_in_assets(name: str, path: Path = ASSETS_INGREDIENTS_PATH) -> None:
    if not name:
        return
    try:
        index = load_ingredient_index(path)
    except Exception as exc:
        print(f"WARNING: Unable to load ingredients asset: {exc}")
        return

    normalized = normalize_ingredient_name(name)
    if not normalized:
        return
    if normalized in index["by_name"]:
        return

    template = None
    for entry in index["raw"]:
        if isinstance(entry, dict) and entry.get("name") and entry.get("nutrition_per_gram"):
            template = entry
            break
    if template is None:
        template = {"id": "", "name": "", "nutrition_per_gram": {}}

    new_id = _slugify_id(name)
    existing_ids = {normalize_ingredient_name(item.get("id")) for item in index["items"]}
    if normalize_ingredient_name(new_id) in existing_ids:
        suffix = 2
        while normalize_ingredient_name(f"{new_id}_v{suffix}") in existing_ids:
            suffix += 1
        new_id = f"{new_id}_v{suffix}"

    nutrition_template = template.get("nutrition_per_gram") or {}
    nutrition_entry = {
        key: 0.0 for key in nutrition_template.keys() if isinstance(key, str)
    }
    if not nutrition_entry:
        nutrition_entry = {
            "calories": 0.0,
            "protein_g": 0.0,
            "fat_g": 0.0,
            "carbs_g": 0.0,
        }

    new_entry = {}
    for key, value in template.items():
        if key == "id":
            new_entry[key] = new_id
        elif key == "name":
            new_entry[key] = name
        elif key == "nutrition_per_gram":
            new_entry[key] = nutrition_entry
        elif isinstance(value, list):
            new_entry[key] = []
        elif isinstance(value, dict):
            new_entry[key] = {}
        elif isinstance(value, (int, float)):
            new_entry[key] = 0
        elif isinstance(value, str):
            new_entry[key] = ""
        else:
            new_entry[key] = None

    if "status" not in new_entry and "needs_review" not in new_entry:
        new_entry["status"] = "incomplete"

    index["raw"].append(new_entry)

    try:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(index["raw"], handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    except OSError as exc:
        print(f"WARNING: Unable to write ingredients asset: {exc}")


def _parse_quantity(value) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    if "/" in text:
        # Handle simple fractions like "1/2"
        parts = text.split("/")
        if len(parts) == 2:
            try:
                return float(parts[0]) / float(parts[1])
            except (TypeError, ValueError, ZeroDivisionError):
                pass
    match = re.search(r"[-+]?\d*\.?\d+", text)
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            return 0.0
    return 0.0


def convert_to_grams(
    amount, unit: Optional[str], ingredient_entry: Optional[Dict]
) -> Tuple[float, Optional[str]]:
    qty = _parse_quantity(amount)
    if qty == 0.0:
        return 0.0, "missing_quantity"

    unit_norm = (unit or "").strip().lower()
    unit_norm = unit_norm.replace(".", "")

    weight_units = {
        "g": 1.0,
        "gram": 1.0,
        "grams": 1.0,
        "kg": 1000.0,
        "kilogram": 1000.0,
        "kilograms": 1000.0,
        "oz": 28.3495,
        "ounce": 28.3495,
        "ounces": 28.3495,
        "lb": 453.592,
        "pound": 453.592,
        "pounds": 453.592,
    }
    if unit_norm in weight_units:
        return qty * weight_units[unit_norm], None

    entry = ingredient_entry or {}
    grams_per_unit = None
    if unit_norm in ("cup", "cups"):
        grams_per_unit = entry.get("grams_per_cup")
    elif unit_norm in ("tbsp", "tablespoon", "tablespoons"):
        grams_per_unit = entry.get("grams_per_tbsp")
    elif unit_norm in ("tsp", "teaspoon", "teaspoons"):
        grams_per_unit = entry.get("grams_per_tsp")
    elif unit_norm in ("ml", "milliliter", "milliliters"):
        density = entry.get("density_g_per_ml")
        if density:
            grams_per_unit = density
    elif unit_norm in ("l", "liter", "liters"):
        density = entry.get("density_g_per_ml")
        if density:
            grams_per_unit = density * 1000.0
    elif not unit_norm:
        grams_per_unit = entry.get("grams_per_unit")

    if grams_per_unit:
        try:
            return qty * float(grams_per_unit), None
        except (TypeError, ValueError):
            return 0.0, "missing_conversion"

    return 0.0, "missing_conversion"


def compute_recipe_macros(
    ingredients: Iterable[Dict], ingredient_index: Dict[str, Dict]
) -> Tuple[Dict[str, float], bool]:
    totals = {
        "calories_kcal": 0.0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
    }
    if not ingredients:
        return totals, False

    missing_data = False
    by_name = ingredient_index.get("by_name", {})
    by_id = ingredient_index.get("by_id", {})

    for ingredient in ingredients:
        if not isinstance(ingredient, dict):
            continue
        name = ingredient.get("name")
        if not name:
            continue
        name_key = normalize_ingredient_name(name)
        entry = by_name.get(name_key) or by_id.get(name_key)
        if not entry:
            missing_data = True
            continue

        grams, issue = convert_to_grams(
            ingredient.get("quantity"),
            ingredient.get("unit"),
            entry,
        )
        if grams == 0.0:
            if issue != "missing_quantity":
                missing_data = True
            continue

        nutrition = entry.get("nutrition_per_gram")
        if not isinstance(nutrition, dict):
            missing_data = True
            continue

        try:
            totals["calories_kcal"] += grams * float(nutrition.get("calories", 0.0) or 0.0)
            totals["protein_g"] += grams * float(nutrition.get("protein_g", 0.0) or 0.0)
            totals["carbs_g"] += grams * float(nutrition.get("carbs_g", 0.0) or 0.0)
            totals["fat_g"] += grams * float(nutrition.get("fat_g", 0.0) or 0.0)
        except (TypeError, ValueError):
            missing_data = True

    return totals, missing_data
