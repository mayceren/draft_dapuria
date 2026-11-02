"""Pantry-first app selection over relevant candidates, keeping WLC scores intact."""

from __future__ import annotations

import re

from .main_ingredients import is_main_ingredient
from .preprocessing import ingredient_matches

TITLE_QUALIFIERS = frozenset({
    "bumbu", "bombay", "simple", "simpel", "sederhana", "praktis", "rumahan", "enak", "lezat",
})
DISTINCT_METHODS = frozenset({
    "sate", "bakar", "panggang", "goreng", "katsu", "teriyaki", "semur", "opor", "rendang",
    "soto", "sop", "sup", "balado", "rica", "tongseng", "tumis", "kukus", "geprek", "kari",
})
FOOD_ANCHORS = frozenset({
    "ayam", "sapi", "ikan", "tahu", "tempe", "telur", "udang", "cumi", "bebek", "kambing",
    "jamur", "terong", "nasi", "kentang",
})


def recipe_family(title: str) -> str:
    title = re.sub(r"^\s*\d+[\s.)\-:]+", "", title.lower())
    words = re.findall(r"\w+", title)
    words = [word for word in words if word not in TITLE_QUALIFIERS]
    if "kecap" in words and not DISTINCT_METHODS.intersection(words):
        anchors = sorted(FOOD_ANCHORS.intersection(words))
        if anchors:
            return " ".join([*anchors, "kecap"])
    return " ".join(words)


def select_pantry_recipes(candidates: list[dict], ingredients: list[str], limit: int) -> list[dict]:
    main_items = [item for item in ingredients if is_main_ingredient(item)]
    eligible = [row for row in candidates if any(
        ingredient_matches(main, name) for main in main_items for name in row["ingredient_names"]
    )]
    eligible.sort(key=lambda row: (
        len(row["missing_items"]), -row["coverage_user"], -row["final_score"], str(row["id"]),
    ))
    selected = []
    seen = set()
    for row in eligible:
        family = recipe_family(row.get("title", "")) or str(row["id"])
        if family in seen:
            continue
        selected.append(row)
        seen.add(family)
        if len(selected) == limit:
            break
    return selected
