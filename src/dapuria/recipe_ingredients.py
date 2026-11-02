"""Repair legacy ingredient metadata using uniquely matching corpus records."""

from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .preprocessing import clean_recipe_ingredients


@lru_cache(maxsize=4)
def _corpus_corrections(path: str, modified_ns: int) -> dict[tuple, tuple[str, ...]]:
    variants: dict[tuple, set[tuple[str, ...]]] = {}
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                names = json.loads(row.get("ingredient_names") or "[]")
                raw = json.loads(row.get("ingredients") or "[]")
            except (ValueError, TypeError):
                continue
            if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
                continue
            if not isinstance(raw, list) or not raw or not all(isinstance(name, str) for name in raw):
                continue
            cleaned = tuple(clean_recipe_ingredients(raw))
            if cleaned:
                key = (row.get("title_clean", ""), tuple(names))
                variants.setdefault(key, set()).add(cleaned)
    # Never guess between conflicting corpus records with the same lookup key.
    return {key: next(iter(items)) for key, items in variants.items() if len(items) == 1}


def prepare_recipe_ingredients(recipe: dict[str, Any], corpus_path: Path | None = None) -> dict[str, Any]:
    source = list(recipe.get("source_ingredient_names", recipe.get("ingredient_names", [])))
    names = clean_recipe_ingredients(recipe.get("ingredient_names", []))
    if corpus_path is not None and corpus_path.is_file():
        key = (recipe.get("title", ""), tuple(source))
        corrected = _corpus_corrections(str(corpus_path.resolve()), corpus_path.stat().st_mtime_ns).get(key)
        if corrected is not None:
            names = list(corrected)
    return {**recipe, "source_ingredient_names": source,
            "ingredient_names": names, "num_ingredients": len(names)}
