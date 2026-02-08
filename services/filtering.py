from typing import Iterable, List, Optional


def _normalize_tags(values: Optional[Iterable]) -> List[str]:
    normalized = []
    seen = set()
    for raw in values or []:
        if raw is None:
            continue
        if hasattr(raw, "name"):
            raw = raw.name
        elif isinstance(raw, dict) and "name" in raw:
            raw = raw.get("name")
        text = str(raw).strip().lower()
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _extract_ingredient_tags(ingredient) -> List[str]:
    if ingredient is None:
        return []
    if isinstance(ingredient, dict):
        return _normalize_tags(ingredient.get("dietary_tags") or [])
    if hasattr(ingredient, "dietary_tags"):
        return _normalize_tags(getattr(ingredient, "dietary_tags"))
    return []


def filter_ingredients_by_dietary_tags(ingredients, selected_tags, mode):
    """
    Filter ingredients by dietary tags.

    AND mode: ingredient must include ALL selected tags.
    OR mode: ingredient must include AT LEAST ONE selected tag.
    Missing/empty tags never match when filters are selected.
    Invalid mode defaults to OR.
    """
    normalized_selected = _normalize_tags(selected_tags)
    if not normalized_selected:
        return list(ingredients or [])

    mode_value = (mode or "or").strip().lower()
    if mode_value not in ("and", "or"):
        mode_value = "or"

    filtered = []
    for ingredient in ingredients or []:
        tags = _extract_ingredient_tags(ingredient)
        if not tags:
            continue
        if mode_value == "and":
            if all(tag in tags for tag in normalized_selected):
                filtered.append(ingredient)
        else:
            if any(tag in tags for tag in normalized_selected):
                filtered.append(ingredient)
    return filtered
