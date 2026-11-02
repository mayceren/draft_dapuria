from __future__ import annotations

import html
import re
from functools import lru_cache

INGREDIENT_ALIASES = {"telor": "telur", "baput": "bawang putih", "bawput": "bawang putih", "bamer": "bawang merah"}
ALIAS_PATTERN = re.compile(r"\b(?:" + "|".join(map(re.escape, INGREDIENT_ALIASES)) + r")\b")
FRACTIONS = {"½": "1/2", "¼": "1/4", "¾": "3/4", "⅓": "1/3", "⅔": "2/3",
             "⅛": "1/8", "⅜": "3/8", "⅝": "5/8", "⅞": "7/8"}
# These product names describe a different pantry item from their source food.
# Keep the same product category on both sides of a phrase match; e.g. generic
# "kaldu" can match "kaldu ayam", while "ayam" cannot.
PRODUCT_MARKERS = frozenset({"kaldu", "terasi", "petis", "kerupuk"})

UNITS = [
    "sendok makan",
    "sendok teh",
    "sdm",
    "sdt",
    "gram",
    "g",
    "gr",
    "kg",
    "ons",
    "ml",
    "mil",
    "mili",
    "liter",
    "ltr",
    "l",
    "butir",
    "btr",
    "buah",
    "bh",
    "siung",
    "lembar",
    "lbr",
    "batang",
    "btg",
    "ikat",
    "ruas",
    "cm",
    "potong",
    "ptg",
    "biji",
    "bj",
    "ekor",
    "ekr",
    "genggam",
    "bungkus",
    "bks",
    "sachet",
    "sct",
    "papan",
    "buku",
    "helai",
    "hlai",
    "gelas",
    "gls",
    "cup",
    "mangkuk",
    "piring",
    "porsi",
    "centong",
    "sisir",
    "kotak",
    "ktk",
    "kaleng",
    "klg",
    "botol",
    "btl",
]
UNITS_SORTED = sorted(UNITS, key=len, reverse=True)
UNIT_PATTERN = "|".join(re.escape(u) for u in UNITS_SORTED)
QTY_PATTERN = (
    r"\d+\s*-\s*\d+"
    r"|\d+\s+\d+\s*/\s*\d+"
    r"|\d+\s*/\s*\d+"
    r"|\d+[.,]\d+"
    r"|\d+"
    r"|sesuai selera"
    r"|secukupnya"
    r"|sejumput"
    r"|beberapa"
    r"|sedikit"
)
INGREDIENT_REGEX = re.compile(
    rf"^\s*(?P<qty>{QTY_PATTERN})?\s*(?:(?P<unit>{UNIT_PATTERN})\b)?\.?\s*(?P<name>.+?)\s*$",
    re.IGNORECASE,
)
MEASUREMENT = re.compile(
    rf"(?<!\w)(?:\d+\s*-\s*\d+|\d+\s+\d+\s*/\s*\d+|\d+\s*/\s*\d+|\d+[.,]\d+|\d+)"
    rf"\s*(?:{UNIT_PATTERN})\b", re.IGNORECASE,
)
PREPARATION_SUFFIX = re.compile(
    r"(?:\s+|,\s*)(?:iris|diiris|potong|dipotong|cincang|dicincang|geprek|digeprek"
    r"|parut|diparut|cuci|dicuci|kupas|dikupas|memarkan|dimemarkan|haluskan|dihaluskan"
    r"|sesuai\s+selera|secukupnya|untuk|utk|buat)\b.*$", re.IGNORECASE,
)
RECIPE_SECTION_NAMES = frozenset({
    "bahan", "bahan utama", "bahan pelengkap", "pelengkap", "bumbu", "bumbu halus",
    "bumbu marinasi", "bahan marinasi", "bahan saus", "bahan sambal",
})
SEASONING_NAME = r"(?:kecap(?: manis| asin)?|garam|gula|lada(?: hitam)?(?: bubuk)?|merica(?: hitam)?(?: bubuk)?)"

# Apply these rules only to user messages, never to corpus ingredient names.
SUBJECT = r"(?:aku|saya|gue|gua|kami|kita)"
MODIFIERS = r"(?:(?:cuma|hanya|masih|kebetulan|sekarang|lagi|juga)\s+)*"
USER_PREFIXES = tuple(re.compile(pattern, re.IGNORECASE) for pattern in (
    r"^(?:halo|hai|hei|hey)(?:\s+(?:dapuria|kak|min))?[\s,:.!]+",
    r"^di\s+(?:rumah|dapur|kulkas)(?:ku)?\s*[:,]?\s*",
    rf"^bahan(?:-bahan)?\s+yang\s+(?:{SUBJECT}\s+)?(?:punya|miliki|ada)\s*[:,]?\s*",
    r"^bahan(?:-bahan)?\s*:\s*",
    (rf"^(?:(?:tolong|coba|bantu(?:in)?(?:\s+{SUBJECT})?)\s+)?"
    r"(?:cari(?:kan)?|rekomendasi(?:kan)?)\s+(?:resep|menu|masakan)\b"
    r"(?:\s+(?:dari|dengan|pakai|pake|berbahan)(?:\s+(?:bahan|dasar))?)?\s*[:,]?\s*"),
    rf"^(?:{SUBJECT}\s+)?(?:mau|ingin|pengen)\s+masak\s+(?:pakai|pake|dengan|dari)\s+",
    rf"^(?:{SUBJECT}\s+)?{MODIFIERS}(?:punya|memiliki|ada(?:nya)?|tersedia)\b\s*{MODIFIERS}[:,]?\s*",
    r"^yang\s+(?:ada(?:nya)?|tersedia)\b\s*[:,]?\s*",
    r"^(?:cuma|hanya)\s+",
))
USER_SUFFIX = re.compile(
    r"(?:\s+(?:nih|dong|ya|yah|saja|aja|doang|kok|secukupnya)"
    r"|\s+(?:(?:juga|yang)\s+)?(?:ada|tersedia)"
    r"|\s+di\s+(?:rumah|dapur|kulkas)(?:ku)?)$", re.IGNORECASE,
)
REQUEST_SUFFIX = re.compile(
    r"(?:[.!?,]\s*|\s+)(?:(?:bisa|boleh|enaknya|cocoknya)\s+(?:di)?(?:masak|bikin|olah|buat)\b"
    r"|masak\s+apa\b|(?:tolong\s+)?cari(?:kan)?\s+resep\b).*$",
    re.IGNORECASE | re.DOTALL,
)
USER_SEPARATORS = re.compile(
    # A comma between digits belongs to a decimal quantity, e.g. 0,5 kg.
    r"\s*(?:(?<!\d)[,.]|[,.](?!\d)|;|[\r\n!?]+|[&+]"
    r"|\b(?:dan|sama|serta|plus)\b|\bjuga\b(?!\s+(?:punya|memiliki|ada|tersedia)\b)"
    r"|\s+(?=tanpa\b))\s*",
    re.IGNORECASE,
)
UNAVAILABLE = re.compile(
    r"\b(?:tidak|nggak|enggak|gak|ga|ngga|belum|tanpa|bukan|jangan|habis|abis)\b",
    re.IGNORECASE,
)
UNCERTAIN = re.compile(
    r"\b(?:mungkin|kayaknya|sepertinya|entah|atau)\b", re.IGNORECASE,
)
EXPLICIT_AVAILABILITY = re.compile(
    r"\b(?:punya|memiliki|miliki|ada(?:nya)?|tersedia)\b|^(?:cuma|hanya)\b",
    re.IGNORECASE,
)


def _strip_user_framing(text: str) -> str:
    """Remove anchored conversational phrases while preserving compound names."""
    text = text.strip(" \t\r\n.,!?;")
    while True:
        previous = text
        for prefix in USER_PREFIXES:
            text = prefix.sub("", text).strip()
        text = USER_SUFFIX.sub("", text).strip()
        if text == previous:
            return text.strip(" :")


@lru_cache(maxsize=32768)
def normalize_ingredient_name(name: str) -> str:
    """Canonicalize quantities, preparation notes, spacing and registered aliases."""
    name = str(name).lower().strip()
    name = re.sub(r"(?<=\d)(?=[½¼¾⅓⅔⅛⅜⅝⅞])", " ", name).translate(str.maketrans(FRACTIONS))
    name = MEASUREMENT.sub("", name)
    name = PREPARATION_SUFFIX.sub("", name)
    name = re.sub(r"\s+", " ", name)
    name = ALIAS_PATTERN.sub(lambda match: INGREDIENT_ALIASES[match.group()], name).strip(" ,.;:")
    return name if re.search(r"[^\W\d_]", name) else ""


def clean_name(name: str) -> str:
    name = str(name)
    name = re.sub(r"\(.*?\)", "", name)
    return normalize_ingredient_name(name)


def parse_ingredient(raw: str) -> dict[str, str]:
    raw = html.unescape(str(raw)).strip()
    raw = re.sub(r"^[\-\*•]+\s*", "", raw)
    # A decimal comma is part of the quantity, not an ingredient/note separator.
    main = re.sub(r"(?<=\d)(?=[½¼¾⅓⅔⅛⅜⅝⅞])", " ", raw).translate(str.maketrans(FRACTIONS))
    main = re.sub(r"(?<=\d),(?=\d)", ".", main).split(",", 1)[0].strip()
    if (not re.search(r"[^\W\d_]", MEASUREMENT.sub("", main))
            or main.lower() in {*UNITS, "secukupnya", "sesuai selera", "sejumput", "beberapa", "sedikit"}):
        return {"raw": raw, "name": ""}
    match = INGREDIENT_REGEX.match(main)
    name = (
        clean_name(match.group("name"))
        if (match and match.group("name"))
        else clean_name(main)
    )
    if (match and match.group("qty") and not match.group("unit")
            and match.end("qty") < len(main) and main[match.end("qty")].isalnum()):
        # A digit in a product name (e.g. 7up) is not a leading quantity.
        name = clean_name(main)
    return {"raw": raw, "name": name}


def clean_recipe_ingredients(names: list[str]) -> list[str]:
    """Canonical recipe items, with quantities/notes and duplicate labels removed."""
    cleaned = []
    # Only split comma tails that are known ingredient names, not preparation
    # notes or decimal quantities such as '1,5 sdm minyak goreng'.
    parts = [part for raw in names for part in re.split(
        rf",\s*(?={SEASONING_NAME}\s*(?:,|$))", raw, flags=re.IGNORECASE,
    )]
    for raw in parts:
        name = parse_ingredient(raw)["name"]
        # A line such as 'garam dan lada' requires both, not just one match.
        for part in re.split(r"\s+dan\s+|\s*&\s*", name):
            part = normalize_ingredient_name(part)
            pieces = (re.findall(SEASONING_NAME, part)
                      if re.fullmatch(rf"{SEASONING_NAME}(?:\s+{SEASONING_NAME})+", part) else [part])
            for piece in pieces:
                if piece and piece not in RECIPE_SECTION_NAMES and piece not in cleaned:
                    cleaned.append(piece)
    return cleaned


def user_ingredient_text(text: str) -> str:
    """Strip framing before trailing recipe requests so prefixes are preserved."""
    return REQUEST_SUFFIX.sub("", _strip_user_framing(html.unescape(str(text))))


def parse_user_ingredients(text: str) -> list[str]:
    """Extract a deterministic inventory from lists or common Indonesian phrases.

    Negated or uncertain lists stay excluded until a contrast or an explicit
    ownership statement starts a new list. This is not a general language model.
    """
    text = user_ingredient_text(text)
    parsed: list[str] = []
    for clause in re.split(r"\b(?:tapi|tetapi|sedangkan|namun)\b", text, flags=re.IGNORECASE):
        available = True
        for item in USER_SEPARATORS.split(clause):
            item = item.strip()
            if not item:
                continue
            if UNAVAILABLE.search(item):
                available = False
                continue
            if UNCERTAIN.search(item):
                available = False
                continue
            framed = _strip_user_framing(item)
            if EXPLICIT_AVAILABILITY.search(item) or EXPLICIT_AVAILABILITY.search(framed):
                available = True
            if not available:
                continue
            framed = re.sub(r"(?<=\d),(?=\d)", ".", framed)
            name = parse_ingredient(framed)["name"] if framed else ""
            if name:
                parsed.append(name)
    return list(dict.fromkeys(parsed))


def ingredient_matches(user_name: str, recipe_name: str) -> bool:
    """Match aliases and whole phrases within the same product category.

    It avoids substring errors such as ``teri`` matching ``terigu`` while still
    allowing ``ayam`` to match ``dada ayam``. Product markers keep source foods
    distinct from stock, shrimp paste and crackers in both directions.
    """
    user_name = normalize_ingredient_name(user_name)
    recipe_name = normalize_ingredient_name(recipe_name)
    if not user_name or not recipe_name:
        return False
    if user_name == recipe_name:
        return True
    user_products = PRODUCT_MARKERS.intersection(re.findall(r"\w+", user_name))
    recipe_products = PRODUCT_MARKERS.intersection(re.findall(r"\w+", recipe_name))
    if user_products != recipe_products:
        return False
    pattern_u = rf"(?<!\w){re.escape(user_name)}(?!\w)"
    pattern_r = rf"(?<!\w){re.escape(recipe_name)}(?!\w)"
    return bool(re.search(pattern_u, recipe_name) or re.search(pattern_r, user_name))
