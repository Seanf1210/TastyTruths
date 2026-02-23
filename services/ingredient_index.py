import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


ASSETS_INGREDIENTS_PATH = (
    Path(__file__).resolve().parents[1] / "static" / "assets" / "ingredients.json"
)

_CACHE = {
    "mtime": None,
    "index": None,
}


def normalize_term(value: Optional[str]) -> str:
    if not value:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = text.replace(",", "").replace(".", "")
    return text


def _load_raw(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return [entry for entry in data if isinstance(entry, dict) and entry.get("name")]


def load_ingredients_index(path: Optional[Path] = None) -> Dict[str, Dict]:
    if path is None:
        # Resolve lazily so tests can monkeypatch ASSETS_INGREDIENTS_PATH.
        path = ASSETS_INGREDIENTS_PATH
    mtime = path.stat().st_mtime if path.exists() else None
    if _CACHE["index"] is not None and _CACHE["mtime"] == mtime:
        return _CACHE["index"]

    items = _load_raw(path)
    by_id = {}
    by_name = {}
    by_alias = {}

    for entry in items:
        entry_id = entry.get("id")
        if entry_id:
            by_id[normalize_term(entry_id)] = entry
        name = entry.get("name")
        if name:
            by_name[normalize_term(name)] = entry
        aliases = entry.get("aliases") or entry.get("alias") or []
        for alias in aliases if isinstance(aliases, list) else []:
            alias_key = normalize_term(alias)
            if alias_key:
                by_alias[alias_key] = entry

    index = {"items": items, "by_id": by_id, "by_name": by_name, "by_alias": by_alias}
    _CACHE["index"] = index
    _CACHE["mtime"] = mtime
    return index


def match_ingredient_id(name_raw: str, index: Dict[str, Dict]) -> Optional[str]:
    key = normalize_term(name_raw)
    if not key:
        return None
    entry = (
        index.get("by_id", {}).get(key)
        or index.get("by_name", {}).get(key)
        or index.get("by_alias", {}).get(key)
    )
    if entry and entry.get("id"):
        return entry["id"]
    return None


def _rank_suggestion(entry: dict, query: str) -> Tuple[int, str]:
    name = normalize_term(entry.get("name"))
    aliases = entry.get("aliases") or entry.get("alias") or []
    alias_values = [normalize_term(a) for a in aliases if a]

    if name.startswith(query):
        return (0, name)
    if any(alias.startswith(query) for alias in alias_values):
        return (1, name)
    if query in name:
        return (2, name)
    if any(query in alias for alias in alias_values):
        return (3, name)
    return (4, name)


def search_suggestions(q: str, limit: int = 8) -> List[dict]:
    query = normalize_term(q)
    if len(query) < 2:
        return []

    index = load_ingredients_index()
    candidates = []
    for entry in index.get("items", []):
        if not entry.get("id") or not entry.get("name"):
            continue
        rank = _rank_suggestion(entry, query)
        if rank[0] < 4:
            candidates.append((rank, entry))

    candidates.sort(key=lambda item: item[0])
    results = []
    for _, entry in candidates[: max(limit, 1)]:
        results.append(
            {"id": entry.get("id"), "name": entry.get("name"), "category": entry.get("category")}
        )
    return results
