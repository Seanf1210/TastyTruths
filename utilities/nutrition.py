"""Nutrition helpers."""

def compute_total_nutrition(ingredients):
    totals = {
        "calories": 0.0,
        "protein_g": 0.0,
        "fat_g": 0.0,
        "carbs_g": 0.0,
    }
    if not ingredients:
        return totals
    for entry in ingredients:
        if not isinstance(entry, dict):
            continue
        qty_raw = entry.get("quantity_g")
        try:
            qty = float(qty_raw) if qty_raw else 0.0
        except (TypeError, ValueError):
            qty = 0.0
        if qty == 0.0:
            continue
        nutrition = entry.get("nutrition_per_gram") or {}
        if not isinstance(nutrition, dict):
            nutrition = {}
        for key in totals.keys():
            value_raw = nutrition.get(key, 0.0)
            try:
                value = float(value_raw) if value_raw else 0.0
            except (TypeError, ValueError):
                value = 0.0
            totals[key] += qty * value
    return totals
