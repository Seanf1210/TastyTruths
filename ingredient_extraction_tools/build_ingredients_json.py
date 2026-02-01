#!/usr/bin/env python3
"""
Build ingredients.json from USDA FoodData Central CSV exports.



Expected files, ensure they are in cwd/sample for now, you can change the directory below
in DEFAULT_INPUT_DIR:
  food.csv, branded_food.csv, foundation_food.csv, sr_legacy_food.csv, survey_fndds_food.csv,
  wweia_food_category.csv, food_category.csv, food_nutrient.csv, nutrient.csv, measure_unit.csv,
  food_portion.csv, food_attribute.csv, food_attribute_type.csv, food_nutrient_derivation.csv,
  food_nutrient_source.csv, food_nutrient_conversion_factor.csv, food_protein_conversion_factor.csv,
  food_calorie_conversion_factor.csv, input_food.csv, food_component.csv, sub_sample_food.csv,
  sub_sample_result.csv, sample_food.csv, lab_method.csv, lab_method_nutrient.csv, lab_method_code.csv,
  market_acquisition.csv, agricultural_samples.csv, acquisition_samples.csv, microbe.csv,
  fndds_ingredient_nutrient_value.csv, fndds_derivation.csv, food_update_log_entry.csv.

Example:
  python build_ingredients_json.py --batch-size 10 --out ingredients.json
  python build_ingredients_json.py --batch-size 500 --ndjson --out ingredients.ndjson
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
from typing import Dict, Iterable, Iterator, List, Optional, Tuple


base = Path.cwd()
DEFAULT_INPUT_DIR = base / "sample"
DEFAULT_OUTPUT = "ingredients_test.json"

REQUIRED_FILES = [
    "food.csv",
    "branded_food.csv",
    "foundation_food.csv",
    "sr_legacy_food.csv",
    "survey_fndds_food.csv",
    "wweia_food_category.csv",
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


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate ingredients.json from USDA FoodData Central CSV exports.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size for food rows.")
    parser.add_argument("--start", type=int, default=0, help="Row offset into food.csv.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of foods to output.")
    parser.add_argument("--out", type=str, default=DEFAULT_OUTPUT, help="Output file path.")
    parser.add_argument("--ndjson", action="store_true", help="Write NDJSON (one object per line).")
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
) -> List[Dict[str, object]]:
    fdc_ids = {row.get("fdc_id", "").strip() for row in fdc_rows if row.get("fdc_id")}
    fdc_ids.discard("")

    branded = load_rows_by_fdc(base_dir / "branded_food.csv", fdc_ids)
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

    ingredients: List[Dict[str, object]] = []
    for row in fdc_rows:
        fdc_id_raw = row.get("fdc_id", "").strip()
        if not fdc_id_raw:
            continue
        fdc_id = parse_int(fdc_id_raw) or fdc_id_raw
        category = build_category(row.get("food_category_id"), lookups["food_category"])
        survey_row = survey.get(fdc_id_raw)
        wweia = build_wweia(survey_row, lookups["wweia_food_category"])

        ingredient = {
            "fdc_id": fdc_id,
            "name": row.get("description", "").strip(),
            "data_type": row.get("data_type", "").strip(),
            "publication_date": row.get("publication_date", "").strip(),
            "category": category,
            "branded": branded.get(fdc_id_raw),
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

        if not ingredient["branded"]:
            ingredient["branded"] = None
        if not ingredient["foundation"]:
            ingredient["foundation"] = None
        if not ingredient["sr_legacy"]:
            ingredient["sr_legacy"] = None
        if not ingredient["survey_fndds"]:
            ingredient["survey_fndds"] = None
        if not ingredient["wweia"]:
            ingredient["wweia"] = None

        ingredients.append(ingredient)

    return ingredients


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


def write_output(path: Path, ndjson: bool, items: Iterable[Dict[str, object]], first: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if ndjson:
        mode = "w" if first else "a"
        with path.open(mode, encoding="utf-8") as handle:
            for item in items:
                handle.write(json.dumps(item, ensure_ascii=False))
                handle.write("\n")
        return

    if first:
        with path.open("w", encoding="utf-8") as handle:
            handle.write("[\n")
    with path.open("a", encoding="utf-8") as handle:
        for idx, item in enumerate(items):
            if not first or idx > 0:
                handle.write(",\n")
            handle.write(json.dumps(item, ensure_ascii=False, indent=2))
    return


def finalize_json_array(path: Path) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n]\n")


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
    first_write = True

    for batch_index, batch_rows in enumerate(
        iter_food_batches(food_path, args.start, args.batch_size, args.limit)
    ):
        batch_start = time.time()
        ingredients = build_batch(batch_rows, lookups, base_dir)
        write_output(Path(args.out), args.ndjson, ingredients, first_write)
        first_write = False
        total_written += len(ingredients)
        batch_elapsed = time.time() - batch_start
        logging.info(
            "Batch %d | foods=%d | wrote=%d | elapsed=%.2fs",
            batch_index,
            len(batch_rows),
            len(ingredients),
            batch_elapsed,
        )

    if not args.ndjson and total_written > 0:
        finalize_json_array(Path(args.out))

    logging.info("Done. Total ingredients written: %d", total_written)
    return 0


if __name__ == "__main__":
    sys.exit(main())
