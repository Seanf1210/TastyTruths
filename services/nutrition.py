import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


# Central location for ingredient asset file (used by Flask static files)
ASSETS_INGREDIENTS_PATH = (
    Path(__file__).resolve().parents[1] / "static" / "assets" / "ingredients.json"
)


# Map common user-entered ingredient names to canonical ingredient IDs in assets.
INGREDIENT_ALIASES = {
    # Demo Spaghetti Bolognese
    "spaghetti": "spaghetti",
    "ground beef": "ground_beef",
    "onion": "onion",
    "garlic": "garlic",
    "crushed tomatoes": "crushed_tomatoes",
    "olive oil": "olive_oil",
    "salt": None,  # intentionally excluded from nutrition

    # Demo Veggie Stir Fry
    "broccoli": "broccoli",
    "carrot": "carrots",
    "carrots": "carrots",
    "bell pepper": "bell_pepper",
    "bell peppers": "bell_pepper",
    "soy sauce": "soy_sauce",
    "ginger": "ginger",

    # Demo Pancakes
    "flour": "flour",
    "baking powder": "baking_powder",
    "milk": "milk",
    "egg": "egg_large",
    "eggs": "egg_large",
    "butter": "butter",

    # Demo Lemon Herb Chicken
    "chicken thighs": "chicken_thighs",
    "lemon": "lemon",
    "oregano": "oregano",

    # Demo Tomato Soup
    "tomatoes": "tomatoes",
    "cream": "cream",

    # Demo Garden Salad
    "mixed greens": "mixed_greens",
    "cucumber": "cucumber",
    "cucumbers": "cucumber",
    "vinegar": "vinegar",
    "tomato": "tomatoes",

    # Demo Baked Salmon
    "salmon fillets": "salmon_fillet",
    "black pepper": "black_pepper",

    # Demo Veggie Wraps
    "tortillas": "tortillas",
    "hummus": "hummus",
    "spinach": "spinach_raw",

    # Demo Berry Parfait
    "greek yogurt": "greek_yogurt",
    "mixed berries": "mixed_berries",
    "berries": "mixed_berries",
    "granola": "granola",
}



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
    by_alias = {}
    for entry in items:
        name_key = normalize_ingredient_name(entry.get("name"))
        if name_key:
            by_name[name_key] = entry
        entry_id = entry.get("id")
        if entry_id:
            by_id[normalize_ingredient_name(entry_id)] = entry
        aliases = entry.get("aliases") or entry.get("alias") or []
        for alias in aliases if isinstance(aliases, list) else []:
            alias_key = normalize_ingredient_name(alias)
            if alias_key:
                by_alias[alias_key] = entry

    return {"items": items, "by_name": by_name, "by_id": by_id, "by_alias": by_alias, "raw": data}


def ensure_ingredient_exists_in_assets(name: str, path: Path = ASSETS_INGREDIENTS_PATH) -> Optional[str]:
    if not name:
        return None
    try:
        index = load_ingredient_index(path)
    except Exception as exc:
        print(f"WARNING: Unable to load ingredients asset: {exc}")
        return None

    normalized = normalize_ingredient_name(name)
    if not normalized:
        return None

    canonical_id = INGREDIENT_ALIASES.get(normalized)
    if canonical_id:
        canonical_key = normalize_ingredient_name(canonical_id)
        canonical_entry = (
            index["by_id"].get(canonical_key)
            or index["by_name"].get(canonical_key)
            or index.get("by_alias", {}).get(canonical_key)
        )
        if canonical_entry:
            return canonical_entry.get("id")

    existing = (
        index["by_name"].get(normalized)
        or index["by_id"].get(normalized)
        or index.get("by_alias", {}).get(normalized)
    )
    # If the name maps to an incomplete entry but we have a canonical alias, return the canonical.
    if existing and existing.get("status") == "incomplete" and canonical_id:
        canonical_key = normalize_ingredient_name(canonical_id)
        canonical_entry = (
            index["by_id"].get(canonical_key)
            or index["by_name"].get(canonical_key)
            or index.get("by_alias", {}).get(canonical_key)
        )
        if canonical_entry:
            return canonical_entry.get("id")

    if existing:
        return existing.get("id")

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
        return None
    return new_id


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
        "lbs": 453.592,
        "pound": 453.592,
        "pounds": 453.592,
    }
    if unit_norm in weight_units:
        return qty * weight_units[unit_norm], None

    entry = ingredient_entry or {}
    grams_per_unit = None
    issue = None
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

    def _fallback_conversion() -> Optional[float]:
        nonlocal issue
        if qty <= 0 or unit_norm in ("", "to taste", "taste"):
            return None

        name_text = (entry.get("id") or entry.get("name") or "").lower()
        powderish = any(word in name_text for word in ("flour", "powder", "oat", "oats", "meal"))
        liquidish = any(word in name_text for word in ("milk", "oil", "water", "broth", "stock"))

        if unit_norm in ("tbsp", "tablespoon", "tablespoons"):
            issue = "fallback_conversion"
            return 13.5  # approx tbsp of oil/water
        if unit_norm in ("tsp", "teaspoon", "teaspoons"):
            issue = "fallback_conversion"
            return 4.5  # approx tsp
        if unit_norm in ("cup", "cups"):
            issue = "fallback_conversion"
            return 120.0 if powderish else 240.0  # flour-ish vs liquid-ish cup
        if unit_norm in ("clove", "cloves"):
            issue = "fallback_conversion"
            return 3.0  # garlic clove
        if unit_norm in ("small", "smallish"):
            if "onion" in name_text:
                issue = "fallback_conversion"
                return 70.0
            if "carrot" in name_text:
                issue = "fallback_conversion"
                return 50.0
        if unit_norm in ("medium",):
            if "carrot" in name_text:
                issue = "fallback_conversion"
                return 61.0
        return None

    if grams_per_unit:
        try:
            return qty * float(grams_per_unit), issue
        except (TypeError, ValueError):
            return 0.0, "missing_conversion"

    fallback = _fallback_conversion()
    if fallback:
        try:
            return qty * float(fallback), issue or "fallback_conversion"
        except (TypeError, ValueError):
            return 0.0, "missing_conversion"

    return 0.0, "missing_conversion"


def compute_recipe_macros(
    ingredients: Iterable[Dict],
    ingredient_index: Dict[str, Dict],
    *,
    debug: bool = False,
    recipe_name: Optional[str] = None,
    collect_stats: bool = False,
) -> Tuple[Dict[str, float], bool]:
    totals = {
        "calories_kcal": 0.0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
    }
    if not ingredients:
        return (totals, False, {"missing_ingredients": 0, "skipped_unknown_units": 0, "lines": []}) if collect_stats else (totals, False)

    missing_data = False
    by_name = ingredient_index.get("by_name", {})
    by_id = ingredient_index.get("by_id", {})
    by_alias = ingredient_index.get("by_alias", {})

    stats = {"missing_ingredients": 0, "skipped_unknown_units": 0, "lines": []}
    recipe_label = recipe_name or "<unnamed recipe>"
    debug_lines: List[str] = []

    for ingredient in ingredients:
        if not isinstance(ingredient, dict):
            continue
        ingredient_id = ingredient.get("ingredient_id") or ingredient.get("id")
        entry = None
        lookup_key_used = None
        if ingredient_id:
            lookup_key_used = normalize_ingredient_name(ingredient_id)
            entry = by_id.get(lookup_key_used)
        if entry is None:
            name = ingredient.get("name") or ingredient.get("name_raw")
            if not name:
                continue
            name_key = normalize_ingredient_name(name)
            lookup_key_used = name_key

            # Canonicalize using INGREDIENT_ALIASES first
            canonical_id = INGREDIENT_ALIASES.get(name_key)
            if canonical_id:
                canonical_key = normalize_ingredient_name(canonical_id)
                entry = (
                    by_id.get(canonical_key)
                    or by_name.get(canonical_key)
                    or by_alias.get(canonical_key)
                )
                lookup_key_used = canonical_key

            if entry is None:
                entry = by_name.get(name_key) or by_alias.get(name_key) or by_id.get(name_key)
        if not entry:
            missing_data = True
            stats["missing_ingredients"] += 1
            stats["lines"].append(
                {
                    "raw_name": ingredient.get("name") or ingredient.get("name_raw"),
                    "raw_quantity": ingredient.get("quantity"),
                    "raw_unit": ingredient.get("unit"),
                    "normalized_key": lookup_key_used,
                    "matched_id": None,
                    "matched_name": None,
                    "status": None,
                    "grams": 0.0,
                    "issue": "missing_ingredient",
                    "macros": None,
                }
            )
            continue

        # Skip auto-created or otherwise incomplete ingredients to avoid skewing totals.
        if entry.get("status") == "incomplete":
            missing_data = True
            stats["missing_ingredients"] += 1
            stats["lines"].append(
                {
                    "raw_name": ingredient.get("name") or ingredient.get("name_raw"),
                    "raw_quantity": ingredient.get("quantity"),
                    "raw_unit": ingredient.get("unit"),
                    "normalized_key": lookup_key_used,
                    "matched_id": entry.get("id"),
                    "matched_name": entry.get("name"),
                    "status": entry.get("status"),
                    "grams": 0.0,
                    "issue": "incomplete",
                    "macros": None,
                }
            )
            continue

        grams, issue = convert_to_grams(
            ingredient.get("quantity"),
            ingredient.get("unit"),
            entry,
        )
        if grams == 0.0:
            if issue != "missing_quantity":
                missing_data = True
            if issue == "missing_conversion":
                stats["skipped_unknown_units"] += 1
            stats["lines"].append(
                {
                    "raw_name": ingredient.get("name") or ingredient.get("name_raw"),
                    "raw_quantity": ingredient.get("quantity"),
                    "raw_unit": ingredient.get("unit"),
                    "normalized_key": lookup_key_used,
                    "matched_id": entry.get("id"),
                    "matched_name": entry.get("name"),
                    "status": entry.get("status"),
                    "grams": grams,
                    "issue": issue or "missing_quantity",
                    "macros": None,
                }
            )
            continue

        nutrition = entry.get("nutrition_per_gram")
        if not isinstance(nutrition, dict):
            missing_data = True
            stats["missing_ingredients"] += 1
            stats["lines"].append(
                {
                    "raw_name": ingredient.get("name") or ingredient.get("name_raw"),
                    "raw_quantity": ingredient.get("quantity"),
                    "raw_unit": ingredient.get("unit"),
                    "normalized_key": lookup_key_used,
                    "matched_id": entry.get("id"),
                    "matched_name": entry.get("name"),
                    "status": entry.get("status"),
                    "grams": grams,
                    "issue": "missing_nutrition",
                    "macros": None,
                }
            )
            continue

        # If nutrition values are all zero, treat as missing to avoid misleading totals.
        nutrition_values = [nutrition.get(k, 0.0) for k in ("calories", "protein_g", "fat_g", "carbs_g")]
        if all((v is None or float(v) == 0.0) for v in nutrition_values):
            missing_data = True
            stats["missing_ingredients"] += 1
            stats["lines"].append(
                {
                    "raw_name": ingredient.get("name") or ingredient.get("name_raw"),
                    "raw_quantity": ingredient.get("quantity"),
                    "raw_unit": ingredient.get("unit"),
                    "normalized_key": lookup_key_used,
                    "matched_id": entry.get("id"),
                    "matched_name": entry.get("name"),
                    "status": entry.get("status"),
                    "grams": grams,
                    "issue": "zero_nutrition",
                    "macros": None,
                }
            )
            continue

        try:
            line_macros = {
                "calories_kcal": grams * float(nutrition.get("calories", 0.0) or 0.0),
                "protein_g": grams * float(nutrition.get("protein_g", 0.0) or 0.0),
                "carbs_g": grams * float(nutrition.get("carbs_g", 0.0) or 0.0),
                "fat_g": grams * float(nutrition.get("fat_g", 0.0) or 0.0),
            }

            totals["calories_kcal"] += line_macros["calories_kcal"]
            totals["protein_g"] += line_macros["protein_g"]
            totals["carbs_g"] += line_macros["carbs_g"]
            totals["fat_g"] += line_macros["fat_g"]

            stats["lines"].append(
                {
                    "raw_name": ingredient.get("name") or ingredient.get("name_raw"),
                    "raw_quantity": ingredient.get("quantity"),
                    "raw_unit": ingredient.get("unit"),
                    "normalized_key": lookup_key_used,
                    "matched_id": entry.get("id"),
                    "matched_name": entry.get("name"),
                    "status": entry.get("status"),
                    "grams": grams,
                    "issue": issue,
                    "macros": line_macros,
                }
            )
        except (TypeError, ValueError):
            missing_data = True
            stats["missing_ingredients"] += 1
            stats["lines"].append(
                {
                    "raw_name": ingredient.get("name") or ingredient.get("name_raw"),
                    "raw_quantity": ingredient.get("quantity"),
                    "raw_unit": ingredient.get("unit"),
                    "normalized_key": lookup_key_used,
                    "matched_id": entry.get("id"),
                    "matched_name": entry.get("name"),
                    "status": entry.get("status"),
                    "grams": grams,
                    "issue": "type_error",
                    "macros": None,
                }
            )

    if debug:
        debug_lines.append(f"\n[NUTRITION DEBUG] Recipe: {recipe_label}")
        for line in stats["lines"]:
            debug_lines.append(
                "  - "
                f"raw='{line.get('raw_name')}' qty={line.get('raw_quantity')} unit={line.get('raw_unit')} | "
                f"lookup='{line.get('normalized_key')}' | matched_id={line.get('matched_id')} matched_name='{line.get('matched_name')}' "
                f"status={line.get('status')} | grams={round(line.get('grams') or 0.0, 3)} "
                f"issue={line.get('issue')} | "
                f"macros={line.get('macros') or '{}'}"
            )
        debug_lines.append(
            f"  Totals: calories={round(totals['calories_kcal'], 2)} kcal, "
            f"protein={round(totals['protein_g'], 2)} g, carbs={round(totals['carbs_g'], 2)} g, fat={round(totals['fat_g'], 2)} g"
        )
        debug_lines.append(
            f"  Missing items: {stats['missing_ingredients']}, Skipped unknown units: {stats['skipped_unknown_units']}"
        )
        print("\n".join(debug_lines))

    if collect_stats:
        return totals, missing_data, stats

    return totals, missing_data
