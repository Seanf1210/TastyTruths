#!/usr/bin/env python3
"""A copy of build_ingredients.py that only extracts non-branded food items.

Author: Ryan K Nash

NOTE: run python generic_only_extractor.py --start 32880 to avoid the disqualified starting rows
of the files

"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional


base = Path.cwd()
DEFAULT_INPUT_DIR = base / "data"
DEFAULT_OUTPUT = "generic_ingredient_index.ndjson"
DEFAULT_FLUSH_EVERY = 1000

REQUIRED_FILES = [
    "food.csv",
    "foundation_food.csv",
    "sr_legacy_food.csv",
    "survey_fndds_food.csv",
    "food_category.csv",
    "food_nutrient.csv",
    "nutrient.csv",
    "measure_unit.csv",
    "food_portion.csv",
    "food_attribute.csv",
    "food_attribute_type.csv",
    "food_nutrient_derivation.csv",
    "food_nutrient_source.csv",
    "food_nutrient_conversion_factor.csv",
    "food_protein_conversion_factor.csv",
    "food_calorie_conversion_factor.csv",
    "input_food.csv",
    "food_component.csv",
    "sub_sample_food.csv",
    "sub_sample_result.csv",
    "sample_food.csv",
    "lab_method.csv",
    "lab_method_nutrient.csv",
    "lab_method_code.csv",
    "market_acquisition.csv",
    "agricultural_samples.csv",
    "acquisition_samples.csv",
    "microbe.csv",
    "fndds_ingredient_nutrient_value.csv",
    "fndds_derivation.csv",
    "food_update_log_entry.csv",
]

LOOKUP_FILES = [
    "nutrient.csv",
    "measure_unit.csv",
    "food_category.csv",
    "food_attribute_type.csv",
    "food_nutrient_derivation.csv",
    "lab_method.csv",
    "lab_method_code.csv",
    "wweia_food_category.csv",
    "fndds_derivation.csv",
]

ALLOWED_DATA_TYPES = {
    "foundation_food",
    "sr_legacy_food",
    "survey_fndds_food",
}

_logged_food_headers = False


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a generic (non-branded) ingredient index from USDA FoodData Central CSV exports.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size for food rows.")
    parser.add_argument("--start", type=int, default=0, help="Row offset into food.csv.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of foods to output.")
    parser.add_argument(
        "--out",
        type=str,
        default=DEFAULT_OUTPUT,
        help="Output file path (NDJSON).",
    )
    parser.add_argument(
        "--min-quality",
        type=int,
        default=40,
        help="Minimum completeness score to include in ingredient index.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    return parser


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def normalize_header(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[\\s\\-]+", "_", value)
    value = re.sub(r"[^a-z0-9_]+", "", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value


def detect_dialect(sample: str) -> csv.Dialect:
    try:
        dialect = csv.Sniffer().sniff(sample)
        if not getattr(dialect, "delimiter", None) or len(dialect.delimiter) != 1:
            raise csv.Error("Invalid delimiter")
        return dialect
    except (csv.Error, ValueError):
        return csv.get_dialect("excel")


def iter_csv_rows(path: Path) -> Iterator[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        dialect = detect_dialect(sample)
        try:
            reader = csv.reader(handle, dialect)
        except ValueError:
            dialect = csv.get_dialect("excel")
            reader = csv.reader(handle, dialect)
        try:
            headers = next(reader)
        except StopIteration:
            return
        normalized_headers = [normalize_header(h) for h in headers]
        for row in reader:
            if not row:
                continue
            if len(row) < len(normalized_headers):
                row.extend([""] * (len(normalized_headers) - len(row)))
            yield {normalized_headers[i]: row[i] for i in range(len(normalized_headers))}


def parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value


def normalize_name_key(value: str) -> str:
    return slugify(normalize_whitespace(value or ""))


def normalize_data_type(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = normalize_whitespace(value).lower()
    mapping = {
        "branded": "branded_food",
        "foundation": "foundation_food",
        "sr legacy": "sr_legacy_food",
        "survey (fndds)": "survey_fndds_food",
        "survey fndds": "survey_fndds_food",
        "experimental": "experimental_food",
    }
    if normalized in mapping:
        return mapping[normalized]
    slug = slugify(normalized)
    if slug.endswith("_food"):
        return slug
    return f"{slug}_food"


def first_nonempty(row: Dict[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(key, "")
        if value and str(value).strip():
            return str(value).strip()
    return ""


def get_field(row: Dict[str, str], *candidates: str) -> str:
    direct = first_nonempty(row, *candidates)
    if direct:
        return direct

    normalized_candidates = [normalize_header(c) for c in candidates if c]
    normalized_candidate_set = {c for c in normalized_candidates if c}
    if "description" in normalized_candidate_set:
        normalized_candidate_set.update({"de_cription", "decription"})
    normalized = first_nonempty(row, *sorted(normalized_candidate_set))
    if normalized:
        return normalized

    relaxed_candidates = {c.replace("_", "") for c in normalized_candidate_set}
    if not relaxed_candidates:
        return ""
    for key in row.keys():
        normalized_key = normalize_header(key).replace("_", "")
        if normalized_key in relaxed_candidates:
            value = row.get(key, "")
            if value and str(value).strip():
                return str(value).strip()
    return ""


def is_allowed_data_type(value: Optional[str]) -> bool:
    normalized = normalize_data_type(value)
    if normalized in ALLOWED_DATA_TYPES:
        return True
    raw = normalize_whitespace(value or "").lower()
    return raw in {"foundation", "sr legacy", "survey (fndds)", "survey fndds"}


def add_search_terms(terms: List[str], *phrases: Optional[str]) -> None:
    seen = set(terms)
    stop_words = {"and", "or", "with", "the", "a", "an", "of"}
    for phrase in phrases:
        if not phrase:
            continue
        normalized = normalize_whitespace(phrase).lower()
        if normalized and normalized not in seen:
            terms.append(normalized)
            seen.add(normalized)
        for token in re.split(r"[^a-z0-9]+", normalized):
            if not token or token in stop_words or len(token) < 2:
                continue
            if token not in seen:
                terms.append(token)
                seen.add(token)


def extract_name(fdc_master: Dict[str, object]) -> str:
    name = normalize_whitespace(str(fdc_master.get("name") or "")).strip()
    return name


def extract_category(fdc_master: Dict[str, object]) -> Optional[str]:
    category = fdc_master.get("category") or {}
    description = category.get("description") if isinstance(category, dict) else None
    if description:
        return description
    category_id = category.get("id") if isinstance(category, dict) else None
    if isinstance(category_id, str) and category_id.strip():
        return category_id.strip()
    return None


def build_nutrient_map(nutrients: List[Dict[str, object]]) -> Dict[int, Optional[float]]:
    nutrient_map: Dict[int, Optional[float]] = {}
    for row in nutrients:
        nutrient_id = row.get("nutrient_id")
        amount = row.get("amount")
        if isinstance(nutrient_id, int):
            nutrient_map[nutrient_id] = amount if isinstance(amount, (int, float)) else None
    return nutrient_map


def build_nutrition_per_100g(nutrient_map: Dict[int, Optional[float]]) -> Dict[str, Optional[float]]:
    return {
        "calories_kcal": nutrient_map.get(1008),
        "protein_g": nutrient_map.get(1003),
        "fat_g": nutrient_map.get(1004),
        "carb_g": nutrient_map.get(1005),
        "fiber_g": nutrient_map.get(1079),
        "sugar_g": nutrient_map.get(2000),
        "sodium_mg": nutrient_map.get(1093),
    }


def build_nutrition_per_gram(nutrition_per_100g: Dict[str, Optional[float]]) -> Dict[str, Optional[float]]:
    def per_gram(value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        return value / 100.0

    return {
        "calories_kcal": per_gram(nutrition_per_100g.get("calories_kcal")),
        "protein_g": per_gram(nutrition_per_100g.get("protein_g")),
        "fat_g": per_gram(nutrition_per_100g.get("fat_g")),
        "carb_g": per_gram(nutrition_per_100g.get("carb_g")),
    }


def detect_keywords(text: str, keywords: List[str]) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def build_dietary_flags(source_text: str) -> List[str]:
    gluten_terms = ["wheat", "barley", "rye", "malt", "farina", "semolina", "triticale"]
    dairy_terms = ["milk", "whey", "casein", "lactose", "butter", "cheese", "cream", "yogurt"]
    nut_terms = [
        "almond",
        "walnut",
        "pecan",
        "cashew",
        "pistachio",
        "hazelnut",
        "macadamia",
        "pine nut",
        "brazil nut",
        "peanut",
    ]
    soy_terms = ["soy", "soya", "soybean"]
    lecithin_terms = ["lecithin"]
    meat_terms = ["beef", "chicken", "pork", "fish", "gelatin", "lard", "tallow"]

    text = source_text.lower() if source_text else ""

    contains_gluten = detect_keywords(text, gluten_terms)
    contains_dairy = detect_keywords(text, dairy_terms)
    contains_nuts = detect_keywords(text, nut_terms)
    contains_soy = detect_keywords(text, soy_terms)
    contains_lecithin = detect_keywords(text, lecithin_terms)
    contains_meat = detect_keywords(text, meat_terms)
    contains_egg_or_honey = "egg" in text or "honey" in text

    explicit_gluten_free = "gluten free" in text or "gluten-free" in text
    explicit_dairy_free = "dairy free" in text or "dairy-free" in text
    explicit_soy_free = "soy free" in text or "soy-free" in text
    explicit_nut_free = "nut free" in text or "nut-free" in text

    if contains_meat:
        vegan_flag = "not_vegan"
        vegetarian_flag = "not_vegetarian"
    elif contains_dairy or contains_egg_or_honey:
        vegan_flag = "not_vegan"
        vegetarian_flag = "unknown"
    else:
        vegan_flag = "unknown"
        vegetarian_flag = "unknown"

    if explicit_gluten_free:
        gluten_flag = "gluten_free"
    elif contains_gluten:
        gluten_flag = "contains_gluten"
    else:
        gluten_flag = "unknown"

    if explicit_dairy_free:
        dairy_flag = "dairy_free"
    elif contains_dairy:
        dairy_flag = "contains_dairy"
    else:
        dairy_flag = "unknown"

    if explicit_nut_free:
        nut_flag = "nut_free"
    elif contains_nuts:
        nut_flag = "contains_nuts"
    else:
        nut_flag = "unknown"

    if explicit_soy_free:
        soy_flag = "soy_free"
    elif contains_soy:
        soy_flag = "contains_soy"
    elif contains_lecithin:
        soy_flag = "unknown"
    else:
        soy_flag = "unknown"

    halal_flag = "halal" if "halal" in text else "unknown"
    kosher_flag = "kosher" if "kosher" in text else "unknown"

    return [
        vegan_flag,
        vegetarian_flag,
        gluten_flag,
        dairy_flag,
        nut_flag,
        soy_flag,
        halal_flag,
        kosher_flag,
    ]


def build_quality(
    nutrition_per_100g: Dict[str, Optional[float]],
    name: str,
    category: Optional[str],
    has_ingredients_text: bool,
) -> Dict[str, object]:
    macros = [
        nutrition_per_100g.get("calories_kcal"),
        nutrition_per_100g.get("protein_g"),
        nutrition_per_100g.get("fat_g"),
        nutrition_per_100g.get("carb_g"),
    ]
    has_all_macros = all(value is not None for value in macros)
    has_calories = nutrition_per_100g.get("calories_kcal") is not None
    has_any_nutrition = any(value is not None for value in macros)

    score = 0
    if has_all_macros:
        score += 40
    if has_calories:
        score += 20
    if has_ingredients_text or name:
        score += 20
    if category:
        score += 20
    if score > 100:
        score = 100

    return {
        "has_nutrition": has_any_nutrition,
        "has_ingredients_text": bool(has_ingredients_text),
        "completeness_score": score,
    }


def to_ingredient_index_record(fdc_master: Dict[str, object]) -> Dict[str, object]:
    name = extract_name(fdc_master)
    brand_block = None

    slug = slugify(name) if name else "item"
    brand_slug = ""
    fdc_id = fdc_master.get("fdc_id")
    if brand_slug:
        record_id = f"{slug}_{brand_slug}_{fdc_id}"
    else:
        record_id = f"{slug}_{fdc_id}"

    nutrients = fdc_master.get("nutrients") or []
    nutrient_map = build_nutrient_map(nutrients)
    nutrition_per_100g = build_nutrition_per_100g(nutrient_map)
    nutrition_per_gram = build_nutrition_per_gram(nutrition_per_100g)

    category = extract_category(fdc_master)

    search_terms: List[str] = []
    add_search_terms(search_terms, name)

    ingredients_text = name
    dietary_flags = build_dietary_flags(ingredients_text)

    quality = build_quality(
        nutrition_per_100g,
        name,
        category,
        False,
    )

    data_type = normalize_data_type(str(fdc_master.get("data_type") or "")) or None

    return {
        "id": record_id,
        "fdc_id": fdc_id,
        "name": name,
        "search_terms": search_terms,
        "category": category,
        "data_type": data_type,
        "brand": brand_block,
        "serving": None,
        "nutrition_per_100g": nutrition_per_100g,
        "nutrition_per_gram": nutrition_per_gram,
        "dietary_flags": dietary_flags,
        "quality": quality,
        "source": {
            "publication_date": fdc_master.get("publication_date") or None,
            "data_source": None,
            "food_description": fdc_master.get("food_description") or None,
        },
    }


def load_lookup_table(path: Path, key_field: str) -> Dict[str, Dict[str, str]]:
    data: Dict[str, Dict[str, str]] = {}
    for row in iter_csv_rows(path):
        key = row.get(key_field, "").strip()
        if key:
            data[key] = row
    logging.info("Loaded %s (%d rows)", path.name, len(data))
    return data


def load_wweia_lookup(path: Path) -> Dict[str, Dict[str, str]]:
    data: Dict[str, Dict[str, str]] = {}
    for row in iter_csv_rows(path):
        code = row.get("wweia_food_category", "").strip()
        if code:
            data[code] = row
    logging.info("Loaded %s (%d rows)", path.name, len(data))
    return data


def check_required_files(base_dir: Path) -> None:
    missing = [name for name in REQUIRED_FILES if not (base_dir / name).exists()]
    if missing:
        logging.warning("Missing files (script can still run if unused): %s", ", ".join(missing))


def iter_food_batches(
    path: Path, start: int, batch_size: int, limit: Optional[int]
) -> Iterator[List[Dict[str, str]]]:
    batch: List[Dict[str, str]] = []
    skipped = 0
    produced = 0
    for row in iter_csv_rows(path):
        if skipped < start:
            skipped += 1
            continue
        batch.append(row)
        produced += 1
        if len(batch) >= batch_size:
            yield batch
            batch = []
        if limit is not None and produced >= limit:
            break
    if batch:
        yield batch


def build_batch(
    fdc_rows: List[Dict[str, str]],
    lookups: Dict[str, Dict[str, Dict[str, str]]],
    base_dir: Path,
    *,
    batch_start_index: int,
) -> Iterator[Dict[str, object]]:
    global _logged_food_headers
    if fdc_rows and not _logged_food_headers:
        logging.info("food.csv normalized headers sample: %s", sorted(fdc_rows[0].keys()))
        _logged_food_headers = True
    eligible_rows = []
    for row in fdc_rows:
        data_type_raw = get_field(row, "data_type", "datatype", "dataType")
        if is_allowed_data_type(data_type_raw):
            eligible_rows.append(row)
    if not eligible_rows:
        if fdc_rows:
            example_type = get_field(fdc_rows[0], "data_type", "datatype", "dataType")
            logging.info(
                "No eligible rows in batch (start=%s size=%s). Example data_type=%s keys=%s",
                batch_start_index,
                len(fdc_rows),
                example_type,
                sorted(fdc_rows[0].keys()),
            )
        return iter(())

    fdc_ids = {
        get_field(row, "fdc_id", "fdcid", "fdcId").strip()
        for row in eligible_rows
        if get_field(row, "fdc_id", "fdcid", "fdcId")
    }
    fdc_ids.discard("")

    foundation = load_rows_by_fdc(base_dir / "foundation_food.csv", fdc_ids)
    sr_legacy = load_rows_by_fdc(base_dir / "sr_legacy_food.csv", fdc_ids)
    survey = load_rows_by_fdc(base_dir / "survey_fndds_food.csv", fdc_ids)
    portions = load_rows_by_fdc(base_dir / "food_portion.csv", fdc_ids, multi=True)
    attributes = load_rows_by_fdc(base_dir / "food_attribute.csv", fdc_ids, multi=True)
    components = load_rows_by_fdc(base_dir / "food_component.csv", fdc_ids, multi=True)
    market_acq = load_rows_by_fdc(base_dir / "market_acquisition.csv", fdc_ids, multi=True)
    agricultural = load_rows_by_fdc(base_dir / "agricultural_samples.csv", fdc_ids, multi=True)
    acquisition = load_rows_by_fdc(base_dir / "acquisition_samples.csv", fdc_ids, multi=True)
    microbes = load_rows_by_fdc(base_dir / "microbe.csv", fdc_ids, multi=True)
    input_foods = load_rows_by_fdc(base_dir / "input_food.csv", fdc_ids, multi=True)
    sample_food = load_rows_by_fdc(base_dir / "sample_food.csv", fdc_ids, multi=True)
    sub_sample_food = load_rows_by_fdc(base_dir / "sub_sample_food.csv", fdc_ids, multi=True)

    nutrient_rows_by_fdc = load_rows_by_fdc(base_dir / "food_nutrient.csv", fdc_ids, multi=True)
    all_nutrient_rows = []
    for rows in nutrient_rows_by_fdc.values():
        all_nutrient_rows.extend(rows)
    sub_sample_result = load_rows_by_key(
        base_dir / "sub_sample_result.csv",
        key_field="food_nutrient_id",
        keys={row.get("id", "").strip() for row in all_nutrient_rows if row.get("id")},
    )

    fndds_ingredient_values = load_rows_by_fdc(
        base_dir / "fndds_ingredient_nutrient_value.csv", fdc_ids, fdc_field="fdc_id", multi=True
    )

    for row in eligible_rows:
        fdc_id_raw = get_field(row, "fdc_id", "fdcid", "fdcId").strip()
        if not fdc_id_raw:
            continue
        fdc_id = parse_int(fdc_id_raw) or fdc_id_raw
        food_description = normalize_whitespace(
            get_field(row, "description", "food_description", "foodDescription")
        ).strip()
        if not food_description:
            logging.warning(
                "Missing food description for fdc_id=%s; keys=%s; skipping.",
                fdc_id_raw,
                sorted(row.keys()),
            )
            continue
        category = build_category(
            get_field(row, "food_category_id", "foodcategoryid", "foodCategoryId"),
            lookups["food_category"],
        )
        survey_row = survey.get(fdc_id_raw)
        wweia = build_wweia(survey_row, lookups["wweia_food_category"])

        ingredient = {
            "fdc_id": fdc_id,
            "name": food_description,
            "food_description": food_description,
            "data_type": get_field(row, "data_type", "datatype", "dataType"),
            "publication_date": get_field(
                row, "publication_date", "publicationdate", "publicationDate"
            ),
            "category": category,
            "branded": None,
            "foundation": foundation.get(fdc_id_raw),
            "sr_legacy": sr_legacy.get(fdc_id_raw),
            "survey_fndds": survey_row,
            "wweia": wweia,
            "nutrients": build_nutrients(
                nutrient_rows_by_fdc.get(fdc_id_raw, []), sub_sample_result, lookups, fdc_id_raw
            ),
            "portions": build_portions(portions.get(fdc_id_raw, []), lookups["measure_unit"]),
            "attributes": build_attributes(
                attributes.get(fdc_id_raw, []), lookups["food_attribute_type"]
            ),
            "components": build_components(components.get(fdc_id_raw, [])),
            "input_foods": build_input_foods(input_foods.get(fdc_id_raw, [])),
            "market_acquisition": normalize_single(market_acq.get(fdc_id_raw, [])),
            "agricultural_samples": agricultural.get(fdc_id_raw, []),
            "acquisition_samples": acquisition.get(fdc_id_raw, []),
            "microbes": microbes.get(fdc_id_raw, []),
            "fndds_ingredient_nutrients": build_fndds_ingredient_values(
                fndds_ingredient_values.get(fdc_id_raw, []), lookups["fndds_derivation"]
            ),
        }

        if not ingredient["foundation"]:
            ingredient["foundation"] = None
        if not ingredient["sr_legacy"]:
            ingredient["sr_legacy"] = None
        if not ingredient["survey_fndds"]:
            ingredient["survey_fndds"] = None
        if not ingredient["wweia"]:
            ingredient["wweia"] = None

        yield ingredient


def load_rows_by_fdc(
    path: Path,
    fdc_ids: Iterable[str],
    *,
    fdc_field: str = "fdc_id",
    multi: bool = False,
) -> Dict[str, object]:
    fdc_set = set(fdc_ids)
    if not path.exists():
        return {}
    results: Dict[str, object] = {}
    for row in iter_csv_rows(path):
        fdc_id = row.get(fdc_field, "").strip()
        if not fdc_id or fdc_id not in fdc_set:
            continue
        if multi:
            results.setdefault(fdc_id, []).append(row)
        else:
            results[fdc_id] = row
    return results


def load_rows_by_key(
    path: Path, key_field: str, keys: Iterable[str]
) -> Dict[str, List[Dict[str, str]]]:
    key_set = {key for key in keys if key}
    if not path.exists() or not key_set:
        return {}
    results: Dict[str, List[Dict[str, str]]] = {}
    for row in iter_csv_rows(path):
        key = row.get(key_field, "").strip()
        if not key or key not in key_set:
            continue
        results.setdefault(key, []).append(row)
    return results


def build_category(
    food_category_id: Optional[str], lookup: Dict[str, Dict[str, str]]
) -> Dict[str, Optional[object]]:
    if not food_category_id:
        return {"id": None, "code": None, "description": None}
    record = lookup.get(food_category_id.strip(), {})
    return {
        "id": parse_int(food_category_id) or food_category_id,
        "code": record.get("code"),
        "description": record.get("description"),
    }


def build_wweia(
    survey_row: Optional[Dict[str, str]],
    lookup: Dict[str, Dict[str, str]],
) -> Optional[Dict[str, Optional[object]]]:
    if not survey_row:
        return None
    code = survey_row.get("wweia_category_code", "").strip()
    if not code:
        return None
    wweia = lookup.get(code, {})
    return {
        "code": parse_int(code) or code,
        "description": wweia.get("wweia_food_category_description"),
    }


def build_nutrients(
    nutrient_rows: List[Dict[str, str]],
    sub_sample_result: Dict[str, List[Dict[str, str]]],
    lookups: Dict[str, Dict[str, Dict[str, str]]],
    fdc_id: str,
) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    for row in nutrient_rows:
        if row.get("fdc_id", "").strip() != fdc_id:
            continue
        nutrient_id = row.get("nutrient_id", "").strip()
        nutrient = lookups["nutrient"].get(nutrient_id)
        if nutrient is None:
            logging.warning("Missing nutrient lookup for nutrient_id=%s", nutrient_id)
            name = None
            unit = None
        else:
            name = nutrient.get("name")
            unit = nutrient.get("unit_name")

        derivation = None
        derivation_id = row.get("derivation_id", "").strip()
        if derivation_id:
            derivation_row = lookups["food_nutrient_derivation"].get(derivation_id)
            derivation = {
                "id": parse_int(derivation_id) or derivation_id,
                "code": derivation_row.get("code") if derivation_row else None,
                "description": derivation_row.get("description") if derivation_row else None,
            }

        nutrient_obj = {
            "nutrient_id": parse_int(nutrient_id) or nutrient_id,
            "name": name,
            "unit": unit,
            "amount": parse_float(row.get("amount")),
            "data_points": parse_int(row.get("data_points")) or row.get("data_points"),
            "derivation": derivation,
            "min": parse_float(row.get("min")),
            "max": parse_float(row.get("max")),
            "median": parse_float(row.get("median")),
            "loq": parse_float(row.get("loq")),
            "footnote": row.get("footnote") or None,
            "min_year_acquired": parse_int(row.get("min_year_acquired"))
            or row.get("min_year_acquired"),
            "percent_daily_value": parse_float(row.get("percent_daily_value")),
            "sub_samples": build_sub_samples(row, sub_sample_result, lookups, name),
        }
        results.append(nutrient_obj)
    return results


def build_sub_samples(
    nutrient_row: Dict[str, str],
    sub_sample_result: Dict[str, List[Dict[str, str]]],
    lookups: Dict[str, Dict[str, Dict[str, str]]],
    nutrient_name: Optional[str],
) -> List[Dict[str, object]]:
    nutrient_id = nutrient_row.get("id", "").strip()
    if not nutrient_id:
        return []
    results: List[Dict[str, object]] = []
    for row in sub_sample_result.get(nutrient_id, []):
        lab_method_id = row.get("lab_method_id", "").strip()
        lab_method = lookups["lab_method"].get(lab_method_id, {}) if lab_method_id else {}
        codes = [
            code_row.get("lab_method_code", "")
            for code_row in lookups["lab_method_code"].values()
            if code_row.get("lab_method_id", "") == lab_method_id
        ]
        results.append(
            {
                "adjusted_amount": parse_float(row.get("adjusted_amount")),
                "lab_method": {
                    "id": parse_int(lab_method_id) or lab_method_id,
                    "description": lab_method.get("description"),
                    "technique": lab_method.get("technique"),
                    "codes": [code for code in codes if code],
                }
                if lab_method_id
                else None,
                "nutrient_name": nutrient_name,
            }
        )
    return results


def build_portions(
    portion_rows: List[Dict[str, str]], measure_units: Dict[str, Dict[str, str]]
) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    for row in portion_rows:
        unit_id = row.get("measure_unit_id", "").strip()
        unit = measure_units.get(unit_id, {})
        results.append(
            {
                "amount": parse_float(row.get("amount")),
                "measure_unit": {
                    "id": parse_int(unit_id) or unit_id,
                    "name": unit.get("name"),
                }
                if unit_id
                else {"id": None, "name": None},
                "portion_description": row.get("portion_description") or None,
                "modifier": row.get("modifier") or None,
                "gram_weight": parse_float(row.get("gram_weight")),
                "data_points": parse_int(row.get("data_points")) or row.get("data_points"),
                "footnote": row.get("footnote") or None,
                "min_year_acquired": parse_int(row.get("min_year_acquired"))
                or row.get("min_year_acquired"),
                "seq_num": parse_int(row.get("seq_num")) or row.get("seq_num"),
            }
        )
    return results


def build_attributes(
    attribute_rows: List[Dict[str, str]], attribute_types: Dict[str, Dict[str, str]]
) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    for row in attribute_rows:
        type_id = row.get("food_attribute_type_id", "").strip()
        type_row = attribute_types.get(type_id, {})
        results.append(
            {
                "type": {
                    "id": parse_int(type_id) or type_id,
                    "name": type_row.get("name"),
                    "description": type_row.get("description"),
                }
                if type_id
                else {"id": None, "name": None, "description": None},
                "name": row.get("name") or None,
                "value": row.get("value") or None,
                "seq_num": parse_int(row.get("seq_num")) or row.get("seq_num"),
            }
        )
    return results


def build_components(component_rows: List[Dict[str, str]]) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    for row in component_rows:
        results.append(
            {
                "name": row.get("name") or "",
                "pct_weight": parse_float(row.get("pct_weight")),
                "is_refuse": parse_int(row.get("is_refuse")) or row.get("is_refuse"),
                "gram_weight": parse_float(row.get("gram_weight")),
            }
        )
    return results


def build_input_foods(input_rows: List[Dict[str, str]]) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    for row in input_rows:
        results.append(
            {
                "fdc_id_of_input_food": parse_int(row.get("fdc_id_of_input_food"))
                or row.get("fdc_id_of_input_food"),
                "seq_num": parse_int(row.get("seq_num")) or row.get("seq_num"),
                "amount": parse_float(row.get("amount")),
                "sr_description": row.get("sr_description") or None,
                "unit": row.get("unit") or None,
                "portion_description": row.get("portion_description") or None,
                "gram_weight": parse_float(row.get("gram_weight")),
                "retention_code": row.get("retention_code") or None,
            }
        )
    return results


def build_fndds_ingredient_values(
    rows: List[Dict[str, str]], derivations: Dict[str, Dict[str, str]]
) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    for row in rows:
        derivation_code = row.get("derivation_code", "").strip()
        derivation = derivations.get(derivation_code)
        results.append(
            {
                "ingredient_code": row.get("ingredient_code") or None,
                "ingredient_description": row.get("ingredient_description") or None,
                "nutrient_code": row.get("nutrient_code") or None,
                "nutrient_value": parse_float(row.get("nutrient_value")),
                "nutrient_value_source": row.get("nutrient_value_source") or None,
                "derivation_code": derivation_code or None,
                "derivation_description": derivation.get("description") if derivation else None,
                "start_date": row.get("start_date") or None,
                "end_date": row.get("end_date") or None,
            }
        )
    return results


def normalize_single(rows: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    if not rows:
        return None
    if len(rows) == 1:
        return rows[0]
    return rows[0]


def load_lookups(base_dir: Path) -> Dict[str, Dict[str, Dict[str, str]]]:
    lookups: Dict[str, Dict[str, Dict[str, str]]] = {}
    lookups["nutrient"] = load_lookup_table(base_dir / "nutrient.csv", "id")
    lookups["measure_unit"] = load_lookup_table(base_dir / "measure_unit.csv", "id")
    lookups["food_category"] = load_lookup_table(base_dir / "food_category.csv", "id")
    lookups["food_attribute_type"] = load_lookup_table(base_dir / "food_attribute_type.csv", "id")
    lookups["food_nutrient_derivation"] = load_lookup_table(
        base_dir / "food_nutrient_derivation.csv", "id"
    )
    lookups["lab_method"] = load_lookup_table(base_dir / "lab_method.csv", "id")
    lookups["lab_method_code"] = load_lookup_table(base_dir / "lab_method_code.csv", "id")
    lookups["wweia_food_category"] = load_wweia_lookup(base_dir / "wweia_food_category.csv")
    lookups["fndds_derivation"] = load_lookup_table(base_dir / "fndds_derivation.csv", "derivation_code")
    return lookups


class IndexWriter:
    def __init__(self, path: Path, flush_every: int = DEFAULT_FLUSH_EVERY) -> None:
        self.path = path
        self.flush_every = max(1, flush_every)
        self._handle = None
        self._buffered = 0

    def __enter__(self) -> "IndexWriter":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("w", encoding="utf-8")
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        if self._handle:
            self._handle.flush()
            self._handle.close()

    def write(self, record: Dict[str, object]) -> None:
        if not self._handle:
            raise RuntimeError("IndexWriter is not open.")
        self._handle.write(json.dumps(record, ensure_ascii=False))
        self._handle.write("\n")
        self._buffered += 1
        if self._buffered >= self.flush_every:
            self._handle.flush()
            self._buffered = 0


def test_generic_only_record() -> None:
    sample = {
        "fdc_id": 999001,
        "name": "Baked Potato",
        "food_description": "Baked Potato",
        "data_type": "Foundation",
        "publication_date": "2022-01-01",
        "category": {"id": 1, "code": None, "description": "Vegetables"},
        "nutrients": [
            {"nutrient_id": 1008, "amount": 90.0},
            {"nutrient_id": 1003, "amount": 2.0},
            {"nutrient_id": 1004, "amount": 0.1},
            {"nutrient_id": 1005, "amount": 20.0},
        ],
    }

    record = to_ingredient_index_record(sample)
    assert record["data_type"] == "foundation_food"
    assert record["brand"] is None
    assert record["name"] == "Baked Potato"
    assert str(record["fdc_id"]) in record["id"]

    row = {
        "fdcid": "999001",
        "datatype": "Foundation",
        "description": "Baked Potato",
        "foodcategoryid": "1",
        "publicationdate": "2022-01-01",
    }
    assert is_allowed_data_type(get_field(row, "data_type", "datatype", "dataType"))
    fdc_master = {
        "fdc_id": parse_int(get_field(row, "fdc_id", "fdcid", "fdcId")) or "999001",
        "name": get_field(row, "description", "food_description", "foodDescription"),
        "food_description": get_field(row, "description", "food_description", "foodDescription"),
        "data_type": get_field(row, "data_type", "datatype", "dataType"),
        "publication_date": get_field(row, "publication_date", "publicationdate", "publicationDate"),
        "category": {"id": 1, "code": None, "description": "Vegetables"},
        "nutrients": [
            {"nutrient_id": 1008, "amount": 90.0},
            {"nutrient_id": 1003, "amount": 2.0},
            {"nutrient_id": 1004, "amount": 0.1},
            {"nutrient_id": 1005, "amount": 20.0},
        ],
    }
    record = to_ingredient_index_record(fdc_master)
    assert record["data_type"] == "foundation_food"

    typo_row = {
        "fdcid": "999002",
        "datatype": "Foundation",
        "de_cription": "Roasted Potato",
    }
    assert (
        get_field(typo_row, "description", "food_description", "foodDescription")
        == "Roasted Potato"
    )


def main() -> int:
    args = build_arg_parser().parse_args()
    configure_logging(args.log_level)

    base_dir = DEFAULT_INPUT_DIR
    check_required_files(base_dir)
    food_path = base_dir / "food.csv"
    if not food_path.exists():
        logging.error("food.csv not found in %s", base_dir)
        return 2

    lookups = load_lookups(base_dir)

    total_written = 0

    with IndexWriter(Path(args.out)) as writer:
        for batch_index, batch_rows in enumerate(
            iter_food_batches(food_path, args.start, args.batch_size, args.limit)
        ):
            batch_start = time.time()
            batch_written = 0
            batch_start_index = args.start + (batch_index * args.batch_size)

            for ingredient in build_batch(
                batch_rows, lookups, base_dir, batch_start_index=batch_start_index
            ):
                record = to_ingredient_index_record(ingredient)
                quality = record.get("quality") or {}
                score = quality.get("completeness_score", 0)
                if isinstance(score, int) and score < args.min_quality:
                    continue
                writer.write(record)
                batch_written += 1
                total_written += 1

            batch_elapsed = time.time() - batch_start
            logging.info(
                "Batch %d | foods=%d | wrote=%d | elapsed=%.2fs",
                batch_index,
                len(batch_rows),
                batch_written,
                batch_elapsed,
            )

    logging.info("Done. Total index records written: %d", total_written)
    return 0


if __name__ == "__main__":
    sys.exit(main())
