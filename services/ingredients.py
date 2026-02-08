from typing import Optional

from sqlalchemy import Float, cast, case, func

from services.db import db
from services.models import Ingredient


ALLOWED_NUTRIENT_SORT_KEYS = {
    "calories_kcal": "Calories (kcal)",
    "protein_g": "Protein (g)",
    "carbs_g": "Carbs (g)",
    "fat_g": "Fat (g)",
    "fiber_g": "Fiber (g)",
    "sugar_g": "Sugar (g)",
    "sodium_mg": "Sodium (mg)",
}


def _nutrition_value_expr(sort_key: str):
    nutrition_col = Ingredient.nutrition_per_100g
    bind = db.session.get_bind()
    dialect = bind.dialect.name if bind else ""

    if dialect == "postgresql":
        value_raw = nutrition_col[sort_key].astext
    else:
        value_raw = func.json_extract(nutrition_col, f"$.{sort_key}")

    value_clean = func.nullif(value_raw, "")
    return cast(value_clean, Float)


def build_ingredient_sort(query, sort_key: Optional[str], sort_dir: str):
    """
    Apply stable ingredient ordering by a nutrient value.

    Missing nutrition values ALWAYS sort to the bottom (asc or desc).
    Tie-breakers: lower(Ingredient.name) ASC, then Ingredient.id ASC.
    """
    if not sort_key:
        return query.order_by(func.lower(Ingredient.name).asc(), Ingredient.id.asc())

    value_expr = _nutrition_value_expr(sort_key)
    value_is_null = case((value_expr.is_(None), 1), else_=0)

    if sort_dir == "asc":
        value_order = value_expr.asc()
    else:
        value_order = value_expr.desc()

    return query.order_by(
        value_is_null.asc(),
        value_order,
        func.lower(Ingredient.name).asc(),
        Ingredient.id.asc(),
    )
